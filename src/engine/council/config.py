"""Council configuration loading and models."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from src.config import settings
from src.engine.context import AgentContextConfig, ContextBudget, ContextFilters


@dataclass(frozen=True)
class AgentPreferences:
    theme_weight: float = 0.5
    efficiency_weight: float = 0.25
    budget_weight: float = 0.25
    price_cap_usd: Optional[float] = None


@dataclass(frozen=True)
class AgentConfig:
    agent_id: str
    agent_type: str  # "heuristic" or "llm"
    display_name: Optional[str] = None
    weight: float = 1.0
    model: Optional[str] = None
    temperature: float = 0.3
    preferences: AgentPreferences = field(default_factory=AgentPreferences)
    context: AgentContextConfig = field(default_factory=AgentContextConfig)


@dataclass(frozen=True)
class VotingConfig:
    strategy: str = "borda"  # "borda" or "majority"
    top_k: int = 25


@dataclass(frozen=True)
class RoutingConfig:
    strategy: str = "parallel"  # "parallel", "sequential", "debate"
    agent_ids: list[str] = field(default_factory=list)
    debate_adjudicator_id: Optional[str] = None


@dataclass(frozen=True)
class CouncilConfig:
    version: int = 1
    voting: VotingConfig = field(default_factory=VotingConfig)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    agents: list[AgentConfig] = field(default_factory=list)


DEFAULT_CONFIG = CouncilConfig(
    agents=[
        AgentConfig(agent_id="heuristic-core", agent_type="heuristic"),
        AgentConfig(agent_id="llm-theme", agent_type="llm", model=settings.openai_model),
        AgentConfig(agent_id="llm-budget", agent_type="llm", model=settings.openai_model),
    ]
)


def _deep_merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _parse_preferences(data: dict[str, Any]) -> AgentPreferences:
    return AgentPreferences(
        theme_weight=float(data.get("theme_weight", 0.5)),
        efficiency_weight=float(data.get("efficiency_weight", 0.25)),
        budget_weight=float(data.get("budget_weight", 0.25)),
        price_cap_usd=(
            float(data["price_cap_usd"]) if data.get("price_cap_usd") is not None else None
        ),
    )


def _parse_context_budget(data: dict[str, Any]) -> ContextBudget:
    if not isinstance(data, dict):
        data = {}
    return ContextBudget(
        max_deck_cards=int(data.get("max_deck_cards", 40)),
        max_candidates=int(data.get("max_candidates", 60)),
        max_commander_text_chars=int(data.get("max_commander_text_chars", 1200)),
        max_candidate_oracle_chars=int(data.get("max_candidate_oracle_chars", 600)),
    )


def _parse_context_filters(data: dict[str, Any]) -> ContextFilters:
    if not isinstance(data, dict):
        data = {}
    return ContextFilters(
        include_commander_text=bool(data.get("include_commander_text", True)),
        include_deck_cards=bool(data.get("include_deck_cards", True)),
        include_candidate_oracle=bool(data.get("include_candidate_oracle", True)),
        include_candidate_type_line=bool(data.get("include_candidate_type_line", True)),
        include_candidate_cmc=bool(data.get("include_candidate_cmc", True)),
        include_candidate_price=bool(data.get("include_candidate_price", True)),
    )


def _parse_context(data: dict[str, Any]) -> AgentContextConfig:
    if not isinstance(data, dict):
        data = {}
    budget = _parse_context_budget(data.get("budget", {}))
    filters = _parse_context_filters(data.get("filters", {}))
    return AgentContextConfig(budget=budget, filters=filters)


def _parse_agent(data: dict[str, Any]) -> AgentConfig:
    preferences = _parse_preferences(data.get("preferences", {}))
    context = _parse_context(data.get("context", {}))
    return AgentConfig(
        agent_id=str(data.get("id") or data.get("agent_id") or "agent"),
        agent_type=str(data.get("type") or data.get("agent_type") or "heuristic"),
        display_name=(data.get("display_name") or None),
        weight=float(data.get("weight", 1.0)),
        model=(data.get("model") or None),
        temperature=float(data.get("temperature", 0.3)),
        preferences=preferences,
        context=context,
    )


def _parse_config(data: dict[str, Any]) -> CouncilConfig:
    voting_data = data.get("voting", {}) if isinstance(data, dict) else {}
    voting = VotingConfig(
        strategy=str(voting_data.get("strategy", "borda")),
        top_k=int(voting_data.get("top_k", 25)),
    )

    routing_data = data.get("routing", {}) if isinstance(data, dict) else {}
    routing = RoutingConfig(
        strategy=str(routing_data.get("strategy", "parallel")),
        agent_ids=[str(agent_id) for agent_id in routing_data.get("agent_ids", []) or []],
        debate_adjudicator_id=(
            str(routing_data["debate_adjudicator_id"])
            if routing_data.get("debate_adjudicator_id") is not None
            else None
        ),
    )

    agents_data = data.get("agents", []) if isinstance(data, dict) else []
    agents = [_parse_agent(agent) for agent in agents_data]

    return CouncilConfig(
        version=int(data.get("version", 1)) if isinstance(data, dict) else 1,
        voting=voting,
        routing=routing,
        agents=agents,
    )


def load_council_config(
    config_path: Optional[Path] = None,
    overrides: Optional[dict[str, Any]] = None,
) -> CouncilConfig:
    import yaml

    path = config_path or settings.council_config_path
    data: dict[str, Any] = {}

    if path and path.exists():
        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
            if isinstance(loaded, dict):
                data = loaded

    if overrides:
        data = _deep_merge(data, overrides)

    if not data:
        return DEFAULT_CONFIG

    config = _parse_config(data)
    if not config.agents:
        return DEFAULT_CONFIG

    return config
