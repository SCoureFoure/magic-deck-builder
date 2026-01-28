"""Deck generation routes."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, HTTPException

from src.config import settings
from src.database.engine import get_db
from src.engine.archetypes import compute_identity_from_deck, extract_identity, score_card_for_identity
from src.engine.commander import create_commander_entry, find_commanders
from src.engine.deck_builder import generate_deck_with_attribution
from src.engine.metrics import compute_coherence_metrics
from src.engine.observability import generate_trace_id
from src.engine.validator import validate_deck
from src.database.seed_roles import seed_roles
from src.web.schemas import (
    DeckCardResult,
    DeckGenerationRequest,
    DeckGenerationResponse,
    SourceAttributionResult,
)

router = APIRouter()


@router.post("/api/decks/generate", response_model=DeckGenerationResponse)
def generate_deck_endpoint(request: DeckGenerationRequest) -> DeckGenerationResponse:
    """Generate a 100-card Commander deck."""
    with get_db() as db:
        if request.use_council and not settings.openai_api_key:
            raise HTTPException(
                status_code=400,
                detail="Council mode requires OPENAI_API_KEY to run LLM agents.",
            )
        commanders = find_commanders(db, name_query=request.commander_name, limit=1)

        if not commanders:
            raise HTTPException(
                status_code=404,
                detail=f"Commander '{request.commander_name}' not found",
            )

        commander_card = commanders[0]

        commander = create_commander_entry(db, commander_card)
        if not commander:
            raise HTTPException(
                status_code=500,
                detail="Could not create commander entry",
            )

        seed_roles(db)

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

        is_valid, errors = validate_deck(deck)

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
