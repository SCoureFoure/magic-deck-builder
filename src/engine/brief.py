"""Deck brief data model for deck generation inputs."""
from __future__ import annotations

from dataclasses import field
from typing import Any, Optional

from pydantic import ConfigDict, Field, field_validator, model_validator
from pydantic.dataclasses import dataclass


@dataclass
class ObjectiveWeights:
    """Objective weights from 0.0 to 1.0."""

    power: float = 0.5
    theme: float = 0.5
    budget: float = 0.5
    consistency: float = 0.5
    novelty: float = 0.0


@dataclass
class DeckConstraints:
    """Constraints for deck generation (Phase 0: stored, not enforced)."""

    max_price_usd: Optional[float] = None
    card_price_cap: Optional[float] = None
    must_include: list[str] = field(default_factory=list)
    must_exclude: list[str] = field(default_factory=list)
    seeds: list[str] = field(default_factory=list)


@dataclass
class DeckBrief:
    """Input contract that steers deck generation."""

    commander: str
    seeds: list[str] = field(default_factory=list)
    objectives: ObjectiveWeights = field(default_factory=ObjectiveWeights)
    constraints: DeckConstraints = field(default_factory=DeckConstraints)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(config=ConfigDict(extra="forbid"))
class AgentTask:
    """Shared agent prompt input schema."""

    role: str = Field(min_length=1)
    count: int = Field(gt=0)
    commander_name: str = Field(min_length=1)
    commander_text: str = ""
    deck_cards: list[str] = field(default_factory=list)

    @field_validator("deck_cards", mode="before")
    @classmethod
    def _ensure_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        return value

    @field_validator("deck_cards")
    @classmethod
    def _clean_deck_cards(cls, value: list[Any]) -> list[str]:
        return [str(card).strip() for card in value if str(card).strip()]


@dataclass(config=ConfigDict(extra="forbid"))
class SearchQuery:
    """Validated search query payload for LLM-generated filters."""

    oracle_contains: list[str] = field(default_factory=list)
    type_contains: list[str] = field(default_factory=list)
    cmc_min: Optional[float] = Field(default=None, ge=0)
    cmc_max: Optional[float] = Field(default=None, ge=0)
    colors: list[str] = field(default_factory=list)

    @field_validator("oracle_contains", "type_contains", "colors", mode="before")
    @classmethod
    def _ensure_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        return value

    @field_validator("oracle_contains", "type_contains")
    @classmethod
    def _clean_text_list(cls, value: list[Any]) -> list[str]:
        return [str(item).lower().strip() for item in value if str(item).strip()]

    @field_validator("colors")
    @classmethod
    def _clean_colors(cls, value: list[Any]) -> list[str]:
        return [str(item).upper().strip() for item in value if str(item).strip()]

    @model_validator(mode="after")
    def _validate_bounds(self) -> "SearchQuery":
        if self.cmc_min is not None and self.cmc_max is not None:
            if self.cmc_min > self.cmc_max:
                raise ValueError("cmc_min must be <= cmc_max")
        return self
