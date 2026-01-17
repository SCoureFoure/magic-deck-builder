"""Deck brief data model for deck generation inputs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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

    max_price_usd: float | None = None
    card_price_cap: float | None = None
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
