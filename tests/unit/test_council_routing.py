from src.engine.council.config import AgentConfig, CouncilConfig, RoutingConfig, VotingConfig
from src.engine.council.routing import CouncilRouter


def _config_with_agents(agent_ids: list[str], strategy: str) -> CouncilConfig:
    agents = [AgentConfig(agent_id=agent_id, agent_type="heuristic") for agent_id in agent_ids]
    return CouncilConfig(
        voting=VotingConfig(strategy="borda", top_k=5),
        routing=RoutingConfig(strategy=strategy, agent_ids=agent_ids),
        agents=agents,
    )


def test_parallel_builds_agent_nodes() -> None:
    config = _config_with_agents(["a1", "a2"], "parallel")
    graph = CouncilRouter(config).build_graph()
    assert "agent_a1" in graph.nodes
    assert "agent_a2" in graph.nodes
    assert "aggregate" in graph.nodes


def test_sequential_builds_agent_nodes() -> None:
    config = _config_with_agents(["a1", "a2", "a3"], "sequential")
    graph = CouncilRouter(config).build_graph()
    assert "agent_a1" in graph.nodes
    assert "agent_a2" in graph.nodes
    assert "agent_a3" in graph.nodes
    assert "aggregate" in graph.nodes


def test_debate_uses_subset() -> None:
    config = _config_with_agents(["a1", "a2", "a3"], "debate")
    graph = CouncilRouter(config).build_graph()
    assert "agent_a1" in graph.nodes
    assert "agent_a2" in graph.nodes
    assert "agent_a3" in graph.nodes


def test_fallback_to_parallel_for_unknown_strategy() -> None:
    config = _config_with_agents(["a1"], "unknown")
    graph = CouncilRouter(config).build_graph()
    assert "agent_a1" in graph.nodes
    assert "aggregate" in graph.nodes
