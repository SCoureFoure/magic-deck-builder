"""LangGraph council orchestration for multi-agent card selection."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.database.models import Card, Commander, CouncilAgentOpinion
from src.engine.archetypes import compute_identity_from_deck
from src.engine.context import SourceAttribution
from src.engine.roles import classify_card_role
from src.engine.council.config import load_council_config
from src.engine.council.routing import CouncilRouter

logger = logging.getLogger(__name__)

def _record_agent_opinions(
    session: Session,
    deck_id: int | None,
    commander_id: int,
    role: str,
    config,
    agent_rankings: dict[str, list[str]],
    trace_id: Optional[str],
) -> None:
    if not agent_rankings:
        return
    agent_map = {agent.agent_id: agent for agent in config.agents}
    top_k = config.voting.top_k
    rows: list[CouncilAgentOpinion] = []
    for agent_id, ranking in agent_rankings.items():
        agent = agent_map.get(agent_id)
        if not agent:
            continue
        rows.append(
            CouncilAgentOpinion(
                deck_id=deck_id,
                commander_id=commander_id,
                role=role,
                agent_id=agent.agent_id,
                agent_type=agent.agent_type,
                weight=agent.weight,
                ranking=ranking[:top_k] if ranking else [],
                trace_id=trace_id,
            )
        )
    if rows:
        try:
            session.add_all(rows)
            session.flush()
        except SQLAlchemyError:
            logger.warning("Failed to persist council agent opinions", exc_info=True)


def _build_candidate_pool(
    session: Session,
    role: str,
    color_identity: list[str],
    exclude_ids: set[int],
    limit: int,
) -> list[Card]:
    query = session.query(Card)
    if exclude_ids:
        query = query.filter(Card.id.notin_(exclude_ids))
    query = query.limit(5000)

    eligible: list[Card] = []
    commander_colors = set(color_identity)

    for card in query.all():
        if card.legalities.get("commander") != "legal":
            continue
        card_colors = set(card.color_identity or [])
        if not card_colors.issubset(commander_colors):
            continue
        if classify_card_role(card) != role:
            continue
        eligible.append(card)
        if len(eligible) >= limit:
            break

    return eligible


def build_council_graph(config) -> object:
    router = CouncilRouter(config)
    return router.build_graph()


def select_cards_with_council(
    session: Session,
    commander: Commander,
    deck_cards: list[Card],
    role: str,
    count: int,
    exclude_ids: Optional[set[int]] = None,
    config_path: Optional[str] = None,
    overrides: Optional[dict[str, object]] = None,
    trace_id: Optional[str] = None,
    deck_id: Optional[int] = None,
) -> list[Card]:
    exclude_ids = exclude_ids or set()
    config = load_council_config(
        config_path=(None if config_path is None else Path(config_path)),
        overrides=overrides,
    )

    pool_size = max(count * 6, config.voting.top_k)
    candidates = _build_candidate_pool(
        session,
        role,
        commander.color_identity or [],
        exclude_ids,
        pool_size,
    )

    if not candidates:
        return []

    identity = compute_identity_from_deck(commander.card, deck_cards)

    graph = build_council_graph(config)
    result = graph.invoke(
        {
            "role": role,
            "commander_name": commander.card.name,
            "commander_text": commander.card.oracle_text or "",
            "deck_cards": deck_cards,
            "candidates": candidates,
            "identity": identity,
            "agent_rankings": {},
            "final_ranking": [],
            "config": config,
            "trace_id": trace_id,
        }
    )

    ranked_names = result.get("final_ranking", [])
    _record_agent_opinions(
        session=session,
        deck_id=deck_id,
        commander_id=commander.id,
        role=role,
        config=config,
        agent_rankings=result.get("agent_rankings", {}),
        trace_id=trace_id,
    )
    candidate_map = {card.name: card for card in candidates}
    ranked_cards = [candidate_map[name] for name in ranked_names if name in candidate_map]

    return ranked_cards[:count]


def select_cards_with_council_with_attribution(
    session: Session,
    commander: Commander,
    deck_cards: list[Card],
    role: str,
    count: int,
    exclude_ids: Optional[set[int]] = None,
    config_path: Optional[str] = None,
    overrides: Optional[dict[str, object]] = None,
    trace_id: Optional[str] = None,
    deck_id: Optional[int] = None,
) -> tuple[list[Card], list[SourceAttribution]]:
    exclude_ids = exclude_ids or set()
    config = load_council_config(
        config_path=(None if config_path is None else Path(config_path)),
        overrides=overrides,
    )

    pool_size = max(count * 6, config.voting.top_k)
    candidates = _build_candidate_pool(
        session,
        role,
        commander.color_identity or [],
        exclude_ids,
        pool_size,
    )

    if not candidates:
        return [], []

    max_attribution_cards = min(pool_size, 100)
    source_attribution = SourceAttribution(
        source_type="candidate_pool",
        details={
            "role": role,
            "color_identity": commander.color_identity or [],
            "excluded": len(exclude_ids),
            "limit": pool_size,
            "total_candidates": len(candidates),
        },
        card_ids=[card.id for card in candidates[:max_attribution_cards]],
        card_names=[card.name for card in candidates[:max_attribution_cards]],
    )
    logger.info(
        "Council candidate sources: role=%s sources=%s",
        role,
        json.dumps([asdict(source_attribution)]),
    )

    identity = compute_identity_from_deck(commander.card, deck_cards)

    graph = build_council_graph(config)
    result = graph.invoke(
        {
            "role": role,
            "commander_name": commander.card.name,
            "commander_text": commander.card.oracle_text or "",
            "deck_cards": deck_cards,
            "candidates": candidates,
            "identity": identity,
            "agent_rankings": {},
            "final_ranking": [],
            "config": config,
            "trace_id": trace_id,
        }
    )

    ranked_names = result.get("final_ranking", [])
    _record_agent_opinions(
        session=session,
        deck_id=deck_id,
        commander_id=commander.id,
        role=role,
        config=config,
        agent_rankings=result.get("agent_rankings", {}),
        trace_id=trace_id,
    )
    candidate_map = {card.name: card for card in candidates}
    ranked_cards = [candidate_map[name] for name in ranked_names if name in candidate_map]

    return ranked_cards[:count], [source_attribution]
