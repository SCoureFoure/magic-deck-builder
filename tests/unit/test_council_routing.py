import pytest

pytest.importorskip("langgraph")

from src.engine.council.config import AgentConfig, CouncilConfig, RoutingConfig
from src.engine.council.routing import _build_debate, _resolve_agents


def _agent(agent_id: str, agent_type: str = "heuristic") -> AgentConfig:
    return AgentConfig(agent_id=agent_id, agent_type=agent_type)


def test_resolve_agents_returns_subset_in_order() -> None:
    config = CouncilConfig(
        agents=[_agent("a"), _agent("b"), _agent("c")],
        routing=RoutingConfig(agent_ids=["c", "a"]),
    )
    resolved = _resolve_agents(config)
    assert [agent.agent_id for agent in resolved] == ["c", "a"]


def test_build_debate_uses_explicit_adjudicator() -> None:
    config = CouncilConfig(
        agents=[_agent("a"), _agent("b"), _agent("judge")],
        routing=RoutingConfig(strategy="debate", debate_adjudicator_id="judge"),
    )
    graph = _build_debate(config, config.agents)
    node_ids = set(graph.nodes.keys())
    assert "agent_a" in node_ids
    assert "agent_b" in node_ids
    assert "agent_judge" in node_ids
    assert "start" in node_ids
    assert "aggregate" in node_ids


def test_build_debate_defaults_last_agent_as_adjudicator() -> None:
    config = CouncilConfig(
        agents=[_agent("a"), _agent("b"), _agent("c")],
        routing=RoutingConfig(strategy="debate"),
    )
    graph = _build_debate(config, config.agents)
    node_ids = set(graph.nodes.keys())
    assert "agent_a" in node_ids
    assert "agent_b" in node_ids
    assert "agent_c" in node_ids
