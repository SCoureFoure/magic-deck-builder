"""Commander search and synergy routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import case, func

from src.config import settings
from src.database.engine import get_db
from src.database.models import Card, Commander, CommanderCardSynergy, CommanderCardVote
from src.engine.commander import create_commander_entry, find_commanders, is_commander_eligible, populate_commanders
from src.ingestion.bulk_ingest import ingest_search_results
from src.ingestion.scryfall_client import ScryfallClient
from src.web.schemas import CommanderResult, CommanderSearchResponse, SynergyCardResult

router = APIRouter()


@router.get("/api/commanders", response_model=CommanderSearchResponse)
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


@router.get("/api/commanders/{commander_name}/synergy", response_model=list[SynergyCardResult])
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


@router.get(
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
