"""FastAPI app for commander search UI."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import logging
import random
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import case, func

from src.database.engine import get_db
from src.database.models import (
    Card,
    Commander,
    CommanderCardSynergy,
    CommanderCardVote,
    CouncilAgentOpinion,
    TrainingSession,
    TrainingSessionCard,
)
from src.database.seed_roles import seed_roles
from src.engine.commander import create_commander_entry, find_commanders, is_commander_eligible, populate_commanders
from src.engine.archetypes import compute_identity_from_deck, extract_identity, score_card_for_identity
from src.engine.council.config import load_council_config
from src.engine.council.training import council_training_opinions
from src.engine.deck_builder import generate_deck_with_attribution
from src.engine.metrics import compute_coherence_metrics
from src.engine.observability import generate_trace_id
from src.engine.validator import validate_deck
from src.config import settings
from src.ingestion.bulk_ingest import ingest_search_results
from src.ingestion.scryfall_client import ScryfallClient


class CommanderResult(BaseModel):
    """API response for a commander search result."""

    name: str
    type_line: str
    color_identity: list[str]
    mana_cost: Optional[str]
    cmc: float
    eligibility: Optional[str]
    commander_legal: str
    image_url: Optional[str]
    card_faces: Optional[list[dict[str, Any]]]


class CommanderSearchResponse(BaseModel):
    """API response for commander search."""

    query: str
    count: int
    results: list[CommanderResult]


class DeckGenerationRequest(BaseModel):
    """Request body for deck generation."""

    commander_name: str
    use_llm_agent: bool = False
    use_council: bool = False
    council_config_path: Optional[str] = None
    council_overrides: Optional[dict[str, Any]] = None
    routing_strategy: Optional[str] = None
    routing_agent_ids: Optional[list[str]] = None
    debate_adjudicator_id: Optional[str] = None
    trace_id: Optional[str] = None


class TrainingCard(BaseModel):
    """Card data for training prompts."""

    id: int
    name: str
    type_line: str
    color_identity: list[str]
    mana_cost: Optional[str]
    cmc: float
    oracle_text: Optional[str]
    image_url: Optional[str]
    card_faces: Optional[list[dict[str, Any]]]


class TrainingSessionResponse(BaseModel):
    """Training session payload."""

    session_id: int
    commander: TrainingCard


class TrainingCardResponse(BaseModel):
    """Training card payload."""

    session_id: int
    card: TrainingCard


class TrainingVoteRequest(BaseModel):
    """Synergy vote submission."""

    session_id: int
    card_id: int
    vote: int  # 1 = synergy, 0 = no synergy


class TrainingCardStat(BaseModel):
    """Card-level synergy stats."""

    card_name: str
    yes: int
    no: int
    ratio: float


class TrainingCommanderSummary(BaseModel):
    """Commander-level synergy stats."""

    commander_name: str
    yes: int
    no: int
    ratio: float
    cards: list[TrainingCardStat]


class TrainingStatsResponse(BaseModel):
    """Aggregate training stats."""

    total_votes: int
    commanders: list[TrainingCommanderSummary]


class CouncilOpinion(BaseModel):
    """Council opinion payload for training analysis."""

    agent_id: str
    display_name: str
    agent_type: str
    weight: float
    score: float
    metrics: str
    reason: str


class CouncilAnalysisRequest(BaseModel):
    """Council analysis request for a training card."""

    session_id: int
    card_id: int
    council_config_path: Optional[str] = None
    council_overrides: Optional[dict[str, Any]] = None
    api_key: Optional[str] = None
    routing_strategy: Optional[str] = None
    routing_agent_ids: Optional[list[str]] = None
    debate_adjudicator_id: Optional[str] = None
    trace_id: Optional[str] = None


class CouncilAnalysisResponse(BaseModel):
    """Council analysis response for a training card."""

    session_id: int
    commander_name: str
    card_name: str
    opinions: list[CouncilOpinion]
    trace_id: Optional[str]


class SynergyCardResult(BaseModel):
    """Commander synergy lookup result."""

    card_name: str
    type_line: str
    mana_cost: Optional[str]
    cmc: float
    image_url: Optional[str]
    card_faces: Optional[list[dict[str, Any]]]
    yes: int
    no: int
    ratio: float
    total_votes: int
    legal_for_commander: bool


class DeckCardResult(BaseModel):
    """A card in the generated deck."""

    name: str
    quantity: int
    role: str
    type_line: str
    mana_cost: Optional[str]
    cmc: float
    image_url: Optional[str]
    identity_score: float
    commander_score: float
    deck_score: float


class SourceAttributionResult(BaseModel):
    """Source attribution payload for selections."""

    source_type: str
    details: dict[str, Any]
    card_ids: list[int]
    card_names: list[str]


class DeckGenerationResponse(BaseModel):
    """API response for deck generation."""

    commander_name: str
    total_cards: int
    is_valid: bool
    validation_errors: list[str]
    cards_by_role: dict[str, list[DeckCardResult]]
    metrics: dict[str, Any]
    sources_by_role: dict[str, list[SourceAttributionResult]]
    trace_id: Optional[str]


app = FastAPI(title="Magic Deck Builder API", version="0.1.0")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=settings.cors_allows_credentials(),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> dict[str, Any]:
    """Basic health check endpoint."""
    return {"status": "ok"}


@app.get("/api/commanders", response_model=CommanderSearchResponse)
def search_commanders(
    query: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(10, ge=1, le=50),
    populate: bool = False,
) -> CommanderSearchResponse:
    """Search for commanders by name."""
    with get_db() as db:
        if populate:
            populate_commanders(db)
        results = find_commanders(db, name_query=query, limit=limit)

        if not results and settings.enable_scryfall_fallback:
            client = ScryfallClient()
            try:
                ingest_search_results(
                    db,
                    client,
                    query=f'name:"{query}"',
                    limit=settings.scryfall_fallback_limit,
                )
                results = find_commanders(db, name_query=query, limit=limit)
            except Exception:
                results = []

        if not results:
            raise HTTPException(status_code=404, detail="No commanders found")

        mapped_results: list[CommanderResult] = []
        for card in results:
            is_eligible, reason = is_commander_eligible(card)
            mapped_results.append(
                CommanderResult(
                    name=card.name,
                    type_line=card.type_line,
                    color_identity=card.color_identity or [],
                    mana_cost=card.mana_cost,
                    cmc=card.cmc,
                    eligibility=reason if is_eligible else None,
                    commander_legal=card.legalities.get("commander", "unknown"),
                    image_url=(card.image_uris or {}).get("normal")
                    if card.image_uris
                    else None,
                    card_faces=card.card_faces,
                )
            )

    return CommanderSearchResponse(query=query, count=len(mapped_results), results=mapped_results)


@app.post("/api/decks/generate", response_model=DeckGenerationResponse)
def generate_deck_endpoint(request: DeckGenerationRequest) -> DeckGenerationResponse:
    """Generate a 100-card Commander deck."""
    with get_db() as db:
        if request.use_council and not settings.openai_api_key:
            raise HTTPException(
                status_code=400,
                detail="Council mode requires OPENAI_API_KEY to run LLM agents.",
            )
        # Find commander
        commanders = find_commanders(db, name_query=request.commander_name, limit=1)

        if not commanders:
            raise HTTPException(
                status_code=404,
                detail=f"Commander '{request.commander_name}' not found"
            )

        commander_card = commanders[0]

        # Get or create commander entry
        commander = create_commander_entry(db, commander_card)

        if not commander:
            raise HTTPException(
                status_code=500,
                detail="Could not create commander entry"
            )

        # Seed roles if needed
        seed_roles(db)

        # Generate deck
        trace_id = request.trace_id or generate_trace_id()
        overrides: dict[str, Any] = dict(request.council_overrides or {})
        routing_overrides: dict[str, Any] = {}
        if request.routing_strategy:
            routing_overrides["strategy"] = request.routing_strategy
        if request.routing_agent_ids:
            routing_overrides["agent_ids"] = request.routing_agent_ids
        if request.debate_adjudicator_id:
            routing_overrides["debate_adjudicator_id"] = request.debate_adjudicator_id
        if routing_overrides:
            overrides["routing"] = routing_overrides

        trace_id = request.trace_id or generate_trace_id()
        build_output = generate_deck_with_attribution(
            db,
            commander,
            constraints={
                "use_llm_agent": request.use_llm_agent,
                "use_council": request.use_council,
                "council_config_path": request.council_config_path,
                "council_overrides": overrides or None,
                "trace_id": trace_id,
            },
        )
        deck = build_output.deck

        # Validate deck
        is_valid, errors = validate_deck(deck)

        # Group cards by role
        from collections import defaultdict
        cards_by_role: dict[str, list[DeckCardResult]] = defaultdict(list)

        deck_cards = [
            dc.card
            for dc in deck.deck_cards
            if dc.card.type_line and "land" not in dc.card.type_line.lower()
        ]
        commander_identity = extract_identity(commander_card, [])
        deck_identity = compute_identity_from_deck(commander_card, deck_cards)

        for deck_card in deck.deck_cards:
            role_name = deck_card.role.name if deck_card.role else "unknown"

            commander_score = score_card_for_identity(deck_card.card, commander_identity)
            deck_score = score_card_for_identity(deck_card.card, deck_identity)
            card_result = DeckCardResult(
                name=deck_card.card.name,
                quantity=deck_card.quantity,
                role=role_name,
                type_line=deck_card.card.type_line,
                mana_cost=deck_card.card.mana_cost,
                cmc=deck_card.card.cmc,
                image_url=(deck_card.card.image_uris or {}).get("normal")
                if deck_card.card.image_uris
                else None,
                identity_score=deck_score,
                commander_score=commander_score,
                deck_score=deck_score,
            )
            cards_by_role[role_name].append(card_result)

        # Calculate total cards
        total_cards = sum(dc.quantity for dc in deck.deck_cards)

        metrics = compute_coherence_metrics(deck, deck_identity)

        sources_payload: dict[str, list[SourceAttributionResult]] = {}
        for role_name, sources in build_output.sources_by_role.items():
            sources_payload[role_name] = [
                SourceAttributionResult(
                    source_type=source.source_type,
                    details=source.details,
                    card_ids=source.card_ids,
                    card_names=source.card_names,
                )
                for source in sources
            ]

        return DeckGenerationResponse(
            commander_name=commander_card.name,
            total_cards=total_cards,
            is_valid=is_valid,
            validation_errors=errors,
            cards_by_role=dict(cards_by_role),
            metrics=metrics,
            sources_by_role=sources_payload,
            trace_id=trace_id,
        )


@app.post("/api/training/session/start", response_model=TrainingSessionResponse)
def training_session_start() -> TrainingSessionResponse:
    """Start a new training session with a random commander."""
    with get_db() as db:
        commander = db.query(Commander).order_by(func.random()).first()
        if not commander:
            raise HTTPException(status_code=404, detail="No commanders available")

        commander_card = commander.card

        session = TrainingSession(commander_id=commander.id)
        db.add(session)
        db.flush()

        def to_training_card(card: Card) -> TrainingCard:
            return TrainingCard(
                id=card.id,
                name=card.name,
                type_line=card.type_line,
                color_identity=card.color_identity or [],
                mana_cost=card.mana_cost,
                cmc=card.cmc,
                oracle_text=card.oracle_text,
                image_url=(card.image_uris or {}).get("normal") if card.image_uris else None,
                card_faces=card.card_faces,
            )

        return TrainingSessionResponse(
            session_id=session.id,
            commander=to_training_card(commander_card),
        )


@app.post("/api/training/council/analyze", response_model=CouncilAnalysisResponse)
def training_council_analyze(request: CouncilAnalysisRequest) -> CouncilAnalysisResponse:
    """Analyze a training card using the council agents."""
    with get_db() as db:
        training_session = (
            db.query(TrainingSession).filter(TrainingSession.id == request.session_id).first()
        )
        if not training_session:
            raise HTTPException(status_code=404, detail="Training session not found")

        card = db.query(Card).filter(Card.id == request.card_id).first()
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")

        overrides: dict[str, Any] = dict(request.council_overrides or {})
        routing_overrides: dict[str, Any] = {}
        if request.routing_strategy:
            routing_overrides["strategy"] = request.routing_strategy
        if request.routing_agent_ids:
            routing_overrides["agent_ids"] = request.routing_agent_ids
        if request.debate_adjudicator_id:
            routing_overrides["debate_adjudicator_id"] = request.debate_adjudicator_id
        if routing_overrides:
            overrides["routing"] = routing_overrides

        config = load_council_config(
            config_path=None
            if request.council_config_path is None
            else Path(request.council_config_path),
            overrides=overrides or None,
        )
        if (
            any(agent.agent_type == "llm" for agent in config.agents)
            and not (request.api_key or settings.openai_api_key)
        ):
            raise HTTPException(
                status_code=400,
                detail="Council analysis requires OPENAI_API_KEY to run LLM agents.",
            )

        opinions = council_training_opinions(
            training_session.commander,
            card,
            config_path=request.council_config_path,
            overrides=overrides or None,
            api_key_override=request.api_key,
            trace_id=trace_id,
        )

        opinion_rows = []
        for opinion in opinions:
            opinion_rows.append(
                CouncilAgentOpinion(
                    training_session_id=training_session.id,
                    commander_id=training_session.commander.id,
                    card_id=card.id,
                    role="training",
                    agent_id=opinion.get("agent_id", ""),
                    agent_type=opinion.get("agent_type", ""),
                    weight=float(opinion.get("weight", 1.0)),
                    score=float(opinion["score"]) if opinion.get("score") is not None else None,
                    metrics={"summary": opinion.get("metrics")},
                    rationale=opinion.get("reason"),
                    trace_id=trace_id,
                )
            )
        if opinion_rows:
            try:
                db.add_all(opinion_rows)
                db.flush()
            except Exception:
                logger.warning(
                    "Failed to persist council agent opinions",
                    exc_info=True,
                )

        return CouncilAnalysisResponse(
            session_id=request.session_id,
            commander_name=training_session.commander.card.name,
            card_name=card.name,
            opinions=[CouncilOpinion(**opinion) for opinion in opinions],
            trace_id=trace_id,
        )


@app.get("/api/training/session/{session_id}/next", response_model=TrainingCardResponse)
def training_session_next(session_id: int) -> TrainingCardResponse:
    """Return the next unseen card for a training session."""
    with get_db() as db:
        session = db.query(TrainingSession).filter(TrainingSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        commander = session.commander
        commander_card = commander.card
        commander_colors = set(commander.color_identity or [])
        seen_card_ids = {
            row.card_id
            for row in db.query(TrainingSessionCard.card_id)
            .filter(TrainingSessionCard.session_id == session.id)
            .all()
        }

        candidates = (
            db.query(Card)
            .filter(Card.legalities["commander"].as_string() == "legal")
            .limit(5000)
            .all()
        )
        random.shuffle(candidates)
        chosen: Card | None = None
        for card in candidates:
            if card.id == commander_card.id:
                continue
            if card.id in seen_card_ids:
                continue
            card_colors = set(card.color_identity or [])
            if not card_colors.issubset(commander_colors):
                continue
            chosen = card
            break

        if not chosen:
            raise HTTPException(status_code=404, detail="No candidate cards found")

        db.add(TrainingSessionCard(session_id=session.id, card_id=chosen.id))
        db.flush()

        def to_training_card(card: Card) -> TrainingCard:
            return TrainingCard(
                id=card.id,
                name=card.name,
                type_line=card.type_line,
                color_identity=card.color_identity or [],
                mana_cost=card.mana_cost,
                cmc=card.cmc,
                oracle_text=card.oracle_text,
                image_url=(card.image_uris or {}).get("normal") if card.image_uris else None,
                card_faces=card.card_faces,
            )

        return TrainingCardResponse(
            session_id=session.id,
            card=to_training_card(chosen),
        )


@app.post("/api/training/session/vote")
def training_session_vote(request: TrainingVoteRequest) -> dict[str, Any]:
    """Store a synergy vote (0/1) for a session card."""
    if request.vote not in (0, 1):
        raise HTTPException(status_code=400, detail="Vote must be 0 or 1")

    with get_db() as db:
        session = db.query(TrainingSession).filter(TrainingSession.id == request.session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        session_card = (
            db.query(TrainingSessionCard)
            .filter(
                TrainingSessionCard.session_id == session.id,
                TrainingSessionCard.card_id == request.card_id,
            )
            .first()
        )
        if not session_card:
            raise HTTPException(status_code=400, detail="Card not in session")

        existing_vote = (
            db.query(CommanderCardVote)
            .filter(
                CommanderCardVote.session_id == session.id,
                CommanderCardVote.card_id == request.card_id,
            )
            .first()
        )
        if existing_vote:
            raise HTTPException(status_code=400, detail="Vote already recorded")

        db.add(
            CommanderCardVote(
                session_id=session.id,
                commander_id=session.commander_id,
                card_id=request.card_id,
                vote=request.vote,
            )
        )

        synergy = (
            db.query(CommanderCardSynergy)
            .filter(
                CommanderCardSynergy.commander_id == session.commander_id,
                CommanderCardSynergy.card_id == request.card_id,
            )
            .first()
        )
        if synergy:
            synergy.label = request.vote
        else:
            db.add(
                CommanderCardSynergy(
                    commander_id=session.commander_id,
                    card_id=request.card_id,
                    label=request.vote,
                )
            )

        db.commit()
        return {"status": "ok"}


@app.get("/api/training/stats", response_model=TrainingStatsResponse)
def training_stats() -> TrainingStatsResponse:
    """Return aggregate training stats."""
    with get_db() as db:
        total_votes = db.query(func.count(CommanderCardVote.id)).scalar() or 0

        yes_case = case((CommanderCardVote.vote == 1, 1), else_=0)
        no_case = case((CommanderCardVote.vote == 0, 1), else_=0)

        commander_rows = (
            db.query(
                Commander.id,
                Card.name.label("commander_name"),
                func.sum(yes_case).label("yes"),
                func.sum(no_case).label("no"),
            )
            .join(Commander, Commander.id == CommanderCardVote.commander_id)
            .join(Card, Card.id == Commander.card_id)
            .group_by(Commander.id, Card.name)
            .all()
        )

        card_rows = (
            db.query(
                CommanderCardVote.commander_id,
                Card.name.label("card_name"),
                func.sum(yes_case).label("yes"),
                func.sum(no_case).label("no"),
            )
            .join(Card, Card.id == CommanderCardVote.card_id)
            .group_by(CommanderCardVote.commander_id, Card.name)
            .all()
        )

        commander_stats: dict[int, TrainingCommanderSummary] = {}
        for commander_id, commander_name, yes, no in commander_rows:
            total = (yes or 0) + (no or 0)
            ratio = (yes or 0) / total if total else 0.0
            commander_stats[commander_id] = TrainingCommanderSummary(
                commander_name=commander_name,
                yes=yes or 0,
                no=no or 0,
                ratio=ratio,
                cards=[],
            )

        for commander_id, card_name, yes, no in card_rows:
            total = (yes or 0) + (no or 0)
            ratio = (yes or 0) / total if total else 0.0
            if commander_id not in commander_stats:
                commander_stats[commander_id] = TrainingCommanderSummary(
                    commander_name="Unknown",
                    yes=0,
                    no=0,
                    ratio=0.0,
                    cards=[],
                )
            commander_stats[commander_id].cards.append(
                TrainingCardStat(card_name=card_name, yes=yes or 0, no=no or 0, ratio=ratio)
            )

        commanders = sorted(
            commander_stats.values(),
            key=lambda item: (-(item.yes + item.no), item.commander_name),
        )
        for commander in commanders:
            commander.cards.sort(key=lambda card: (-(card.yes + card.no), card.card_name))
            commander.cards = commander.cards[:10]

        return TrainingStatsResponse(
            total_votes=total_votes,
            commanders=commanders[:10],
        )


@app.get("/api/commanders/{commander_name}/synergy", response_model=list[SynergyCardResult])
def commander_synergy_lookup(
    commander_name: str, query: str = Query(..., min_length=1, max_length=100)
) -> list[SynergyCardResult]:
    """Search cards and return synergy vote ratios for a commander."""
    with get_db() as db:
        commanders = find_commanders(db, name_query=commander_name, limit=1)
        if not commanders:
            raise HTTPException(status_code=404, detail="Commander not found")

        commander_card = commanders[0]
        commander = create_commander_entry(db, commander_card)
        if not commander:
            raise HTTPException(status_code=500, detail="Could not create commander entry")

        commander_colors = set(commander.color_identity or [])

        cards = (
            db.query(Card)
            .filter(Card.name.ilike(f"%{query}%"))
            .limit(25)
            .all()
        )

        if not cards:
            return []

        votes = (
            db.query(
                CommanderCardVote.card_id,
                func.sum(case((CommanderCardVote.vote == 1, 1), else_=0)).label("yes"),
                func.sum(case((CommanderCardVote.vote == 0, 1), else_=0)).label("no"),
            )
            .filter(CommanderCardVote.commander_id == commander.id)
            .group_by(CommanderCardVote.card_id)
            .all()
        )
        vote_map = {card_id: (yes or 0, no or 0) for card_id, yes, no in votes}

        results: list[SynergyCardResult] = []
        for card in cards:
            yes, no = vote_map.get(card.id, (0, 0))
            total = yes + no
            ratio = yes / total if total else 0.0
            card_colors = set(card.color_identity or [])
            legal_for_commander = card_colors.issubset(commander_colors)
            results.append(
                SynergyCardResult(
                    card_name=card.name,
                    type_line=card.type_line,
                    mana_cost=card.mana_cost,
                    cmc=card.cmc,
                    image_url=(card.image_uris or {}).get("normal") if card.image_uris else None,
                    card_faces=card.card_faces,
                    yes=yes,
                    no=no,
                    ratio=ratio,
                    total_votes=total,
                    legal_for_commander=legal_for_commander,
                )
            )

        results.sort(key=lambda item: (-item.ratio, item.card_name))
        return results


@app.get(
    "/api/commanders/{commander_name}/synergy/top",
    response_model=list[SynergyCardResult],
)
def commander_synergy_top(
    commander_name: str,
    limit: int = Query(5, ge=1, le=20),
    min_ratio: float = Query(0.5, ge=0.0, le=1.0),
) -> list[SynergyCardResult]:
    """Return top synergy cards for a commander based on community votes."""
    with get_db() as db:
        commanders = find_commanders(db, name_query=commander_name, limit=1)
        if not commanders:
            raise HTTPException(status_code=404, detail="Commander not found")

        commander_card = commanders[0]
        commander = create_commander_entry(db, commander_card)
        if not commander:
            raise HTTPException(status_code=500, detail="Could not create commander entry")

        commander_colors = set(commander.color_identity or [])

        vote_rows = (
            db.query(
                CommanderCardVote.card_id,
                func.sum(case((CommanderCardVote.vote == 1, 1), else_=0)).label("yes"),
                func.sum(case((CommanderCardVote.vote == 0, 1), else_=0)).label("no"),
            )
            .filter(CommanderCardVote.commander_id == commander.id)
            .group_by(CommanderCardVote.card_id)
            .all()
        )

        candidates: list[tuple[int, int, int, float]] = []
        for card_id, yes, no in vote_rows:
            yes_count = yes or 0
            no_count = no or 0
            total = yes_count + no_count
            if total == 0:
                continue
            ratio = yes_count / total
            if ratio < min_ratio:
                continue
            candidates.append((card_id, yes_count, no_count, ratio))

        if not candidates:
            return []

        candidates.sort(key=lambda item: (-item[3], -(item[1] + item[2])))
        top_ids = [card_id for card_id, _, _, _ in candidates[:limit]]

        cards = db.query(Card).filter(Card.id.in_(top_ids)).all()
        card_map = {card.id: card for card in cards}

        results: list[SynergyCardResult] = []
        for card_id, yes_count, no_count, ratio in candidates[:limit]:
            card = card_map.get(card_id)
            if not card:
                continue
            card_colors = set(card.color_identity or [])
            legal_for_commander = card_colors.issubset(commander_colors)
            results.append(
                SynergyCardResult(
                    card_name=card.name,
                    type_line=card.type_line,
                    mana_cost=card.mana_cost,
                    cmc=card.cmc,
                    image_url=(card.image_uris or {}).get("normal") if card.image_uris else None,
                    card_faces=card.card_faces,
                    yes=yes_count,
                    no=no_count,
                    ratio=ratio,
                    total_votes=yes_count + no_count,
                    legal_for_commander=legal_for_commander,
                )
            )

        results.sort(key=lambda item: (-item.ratio, -item.total_votes, item.card_name))
        return results
