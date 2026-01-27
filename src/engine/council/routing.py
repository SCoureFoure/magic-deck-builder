"""Routing strategies for council agent execution."""
from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from langgraph.graph import END, StateGraph
from typing_extensions import Annotated, TypedDict

from src.engine.council.agents import heuristic_rank_candidates, llm_rank_candidates
from src.engine.council.config import AgentConfig, CouncilConfig
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
    deck_cards: list
    candidates: list
    identity: Optional[dict[str, float]]
    agent_rankings: Annotated[dict[str, list[str]], _merge_rankings]
    final_ranking: list[str]
    config: CouncilConfig


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
        elif agent_type == "llm":
            ranked = llm_rank_candidates(
                agent,
                state["role"],
                state["commander_name"],
                state["commander_text"],
                state["XXdeck_cardsXX"],
                state["candidates"],
            )
            if not ranked:
                ranked = heuristic_rank_candidates(
                    state["candidates"],
                    state["role"],
                    state["identity"],
                    agent.preferences,
                )
        else:
            ranked = heuristic_rank_candidates(
                state["candidates"],
                state["role"],
                state["identity"],
                agent.preferences,
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


StrategyBuilder = Callable[[CouncilConfig, list[AgentConfig]], StateGraph]


def _resolve_agents(config: CouncilConfig) -> list[AgentConfig]:
    routing = config.routing
    if not routing.agent_ids:
        return list(config.agents)
    agent_map = {agent.agent_id: agent for agent in config.agents}
    return [agent_map[agent_id] for agent_id in routing.agent_ids if agent_id in agent_map]


def _build_parallel(config: CouncilConfig, agents: list[AgentConfig]) -> StateGraph:
    graph = StateGraph(CouncilState)
    graph.add_node("start", lambda state: {})
    graph.add_node("aggregate", _aggregate_node)
    for agent in agents:
        graph.add_node(
            f"agent_{agent.agent_id}",
            _agent_node(agent.agent_id, agent.agent_type),
        )
        graph.add_edge("start", f"agent_{agent.agent_id}")
        graph.add_edge(f"agent_{agent.agent_id}", "aggregate")
    graph.set_entry_point("start")
    graph.add_edge("aggregate", END)
    return graph


def _build_sequential(config: CouncilConfig, agents: list[AgentConfig]) -> StateGraph:
    graph = StateGraph(CouncilState)
    graph.add_node("start", lambda state: {})
    graph.add_node("aggregate", _aggregate_node)
    graph.set_entry_point("start")
    previous = "start"
    for agent in agents:
        node_id = f"agent_{agent.agent_id}"
        graph.add_node(node_id, _agent_node(agent.agent_id, agent.agent_type))
        graph.add_edge(previous, node_id)
        previous = node_id
    graph.add_edge(previous, "aggregate")
    graph.add_edge("aggregate", END)
    return graph


def _build_debate(config: CouncilConfig, agents: list[AgentConfig]) -> StateGraph:
    graph = StateGraph(CouncilState)
    graph.add_node("start", lambda state: {})
    graph.add_node("aggregate", _aggregate_node)
    graph.set_entry_point("start")

    adjudicator: Optional[AgentConfig] = None
    if config.routing.debate_adjudicator_id:
        adjudicator = next(
            (agent for agent in agents if agent.agent_id == config.routing.debate_adjudicator_id),
            None,
        )
    if adjudicator is None and len(agents) > 2:
        adjudicator = agents[-1]

    debaters = agents
    if adjudicator and adjudicator in agents:
        debaters = [agent for agent in agents if agent.agent_id != adjudicator.agent_id]
    if len(debaters) > 2:
        debaters = debaters[:2]

    for agent in debaters:
        node_id = f"agent_{agent.agent_id}"
        graph.add_node(node_id, _agent_node(agent.agent_id, agent.agent_type))
        graph.add_edge("start", node_id)

    if adjudicator:
        adjudicator_node = f"agent_{adjudicator.agent_id}"
        graph.add_node(
            adjudicator_node,
            _agent_node(adjudicator.agent_id, adjudicator.agent_type),
        )
        for agent in debaters:
            graph.add_edge(f"agent_{agent.agent_id}", adjudicator_node)
        graph.add_edge(adjudicator_node, "aggregate")
    else:
        for agent in debaters:
            graph.add_edge(f"agent_{agent.agent_id}", "aggregate")

    graph.add_edge("aggregate", END)
    return graph


_STRATEGY_BUILDERS: dict[str, StrategyBuilder] = {
    "parallel": _build_parallel,
    "sequential": _build_sequential,
    "debate": _build_debate,
}


class CouncilRouter:
    """Route agent execution based on strategy."""

    def __init__(self, config: CouncilConfig) -> None:
        self.config = config

    def build_graph(self) -> StateGraph:
        agents = _resolve_agents(self.config)
        if not agents:
            agents = list(self.config.agents)
        builder = _STRATEGY_BUILDERS.get(self.config.routing.strategy, _build_parallel)
        return builder(self.config, agents).compile()
