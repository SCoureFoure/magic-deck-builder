"""Context assembly and attribution for agent prompts."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from src.database.models import Card
from src.engine.brief import AgentTask


@dataclass(frozen=True)
class ContextBudget:
    max_deck_cards: int = 40
    max_candidates: int = 60
    max_commander_text_chars: int = 1200
    max_candidate_oracle_chars: int = 600


@dataclass(frozen=True)
class ContextFilters:
    include_commander_text: bool = True
    include_deck_cards: bool = True
    include_candidate_oracle: bool = True
    include_candidate_type_line: bool = True
    include_candidate_cmc: bool = True
    include_candidate_price: bool = True


@dataclass(frozen=True)
class AgentContextConfig:
    budget: ContextBudget = field(default_factory=ContextBudget)
    filters: ContextFilters = field(default_factory=ContextFilters)


@dataclass(frozen=True)
class DeckContext:
    commander_name: str
    commander_text: str
    deck_cards: list[str]


@dataclass(frozen=True)
class CandidateContext:
    candidates: list[Card]
    payload: list[dict[str, Any]]


@dataclass(frozen=True)
class SourceAttribution:
    source_type: str
    details: dict[str, Any]
    card_ids: list[int] = field(default_factory=list)
    card_names: list[str] = field(default_factory=list)


def _truncate(text: str, max_chars: Optional[int]) -> str:
    if max_chars is None:
        return text
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip()


def build_deck_context(task: AgentTask, config: AgentContextConfig) -> DeckContext:
    deck_cards = list(task.deck_cards) if config.filters.include_deck_cards else []
    if config.budget.max_deck_cards is not None:
        deck_cards = deck_cards[: config.budget.max_deck_cards]

    commander_text = task.commander_text if config.filters.include_commander_text else ""
    commander_text = _truncate(commander_text, config.budget.max_commander_text_chars)

    return DeckContext(
        commander_name=task.commander_name,
        commander_text=commander_text,
        deck_cards=deck_cards,
    )


def build_candidate_context(
    candidates: list[Card], config: AgentContextConfig
) -> CandidateContext:
    limited = candidates
    if config.budget.max_candidates is not None:
        limited = candidates[: config.budget.max_candidates]

    payload: list[dict[str, Any]] = []
    for card in limited:
        entry: dict[str, Any] = {"name": card.name}
        if config.filters.include_candidate_type_line:
            entry["type"] = card.type_line
        if config.filters.include_candidate_cmc:
            entry["cmc"] = card.cmc
        if config.filters.include_candidate_price:
            entry["price_usd"] = card.price_usd
        if config.filters.include_candidate_oracle:
            entry["oracle"] = _truncate(
                card.oracle_text or "",
                config.budget.max_candidate_oracle_chars,
            )
        payload.append(entry)

    return CandidateContext(candidates=limited, payload=payload)


def summarize_context_config(config: AgentContextConfig) -> dict[str, Any]:
    return {
        "budget": asdict(config.budget),
        "filters": asdict(config.filters),
    }
