"""LangGraph council orchestration for multi-agent card selection."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from langgraph.graph import END, StateGraph
from typing_extensions import Annotated, TypedDict
from sqlalchemy.orm import Session

from src.database.models import Card, Commander
from src.engine.archetypes import compute_identity_from_deck
from src.engine.roles import classify_card_role
from src.engine.council.agents import heuristic_rank_candidates, llm_rank_candidates
from src.engine.council.config import CouncilConfig, load_council_config
from src.engine.council.voting import aggregate_rankings


def _merge_rankings(
    existing: dict[str, list[str]] | None,
    incoming: dict[str, list[str]] | None,
) -> dict[str, list[str]]:
    merged = dict(existing or {})
    merged.update(incoming or {})
    return merged


class CouncilState(TypedDict):
    role: str
    commander_name: str
    commander_text: str
    deck_cards: list[Card]
    candidates: list[Card]
    identity: Optional[dict[str, float]]
    agent_rankings: Annotated[dict[str, list[str]], _merge_rankings]
    final_ranking: list[str]
    config: CouncilConfig


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


def _agent_node(agent_id: str, agent_type: str):
    def run(state: CouncilState) -> dict[str, dict[str, list[str]]]:
        agent = next(
            (cfg for cfg in state["config"].agents if cfg.agent_id == agent_id),
            None,
        )
        if not agent:
            return {"agent_rankings": {agent_id: []}}

        if agent_type == "heuristic":
            ranked = heuristic_rank_candidates(
                state["candidates"],
                state["role"],
                state["identity"],
                agent.preferences,
            )
        else:
            ranked = llm_rank_candidates(
                agent,
                state["role"],
                state["commander_name"],
                state["commander_text"],
                state["deck_cards"],
                state["candidates"],
            )
        return {"agent_rankings": {agent_id: ranked}}

    return run


def _aggregate_node(state: CouncilState) -> dict[str, list[str]]:
    weights = {agent.agent_id: agent.weight for agent in state["config"].agents}
    voting = state["config"].voting
    final = aggregate_rankings(
        state.get("agent_rankings", {}),
        weights,
        voting.strategy,
        voting.top_k,
    )
    return {"final_ranking": final}


def build_council_graph(config: CouncilConfig) -> StateGraph:
    graph = StateGraph(CouncilState)

    graph.add_node("start", lambda state: {})
    graph.add_node("aggregate", _aggregate_node)

    for agent in config.agents:
        graph.add_node(
            f"agent_{agent.agent_id}",
            _agent_node(agent.agent_id, agent.agent_type),
        )
        graph.add_edge("start", f"agent_{agent.agent_id}")
        graph.add_edge(f"agent_{agent.agent_id}", "aggregate")
    graph.set_entry_point("start")
    graph.add_edge("aggregate", END)

    return graph.compile()


def select_cards_with_council(
    session: Session,
    commander: Commander,
    deck_cards: list[Card],
    role: str,
    count: int,
    exclude_ids: Optional[set[int]] = None,
    config_path: Optional[str] = None,
    overrides: Optional[dict[str, object]] = None,
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
    result: CouncilState = graph.invoke(
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
        }
    )

    ranked_names = result.get("final_ranking", [])
    candidate_map = {card.name: card for card in candidates}
    ranked_cards = [candidate_map[name] for name in ranked_names if name in candidate_map]

    return ranked_cards[:count]
