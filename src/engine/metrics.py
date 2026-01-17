"""Coherence metrics for deck identity evaluation."""
from __future__ import annotations

from collections import Counter
from typing import Iterable

from src.database.models import Deck


def gini_coefficient(values: Iterable[float]) -> float:
    """Compute Gini coefficient for non-negative values."""
    values_list = [v for v in values if v >= 0]
    if not values_list:
        return 0.0

    values_list.sort()
    total = sum(values_list)
    if total == 0:
        return 0.0

    n = len(values_list)
    cumulative = 0.0
    for i, value in enumerate(values_list, start=1):
        cumulative += i * value

    return (2 * cumulative) / (n * total) - (n + 1) / n


def compute_coherence_metrics(deck: Deck, identity: dict[str, float]) -> dict[str, float]:
    """Compute coarse-grained coherence metrics for Phase 0."""
    identity_values = list(identity.values())
    archetype_purity = max(identity_values) if identity_values else 0.0
    identity_concentration = gini_coefficient(identity_values)

    role_counts = Counter()
    for deck_card in deck.deck_cards:
        role_name = deck_card.role.name if deck_card.role else "unknown"
        role_counts[role_name] += deck_card.quantity

    synergy_count = role_counts.get("synergy", 0)
    nonland_count = sum(
        count for role, count in role_counts.items() if role != "lands"
    )
    synergy_ratio = synergy_count / nonland_count if nonland_count > 0 else 0.0

    return {
        "archetype_purity": archetype_purity,
        "identity_concentration": identity_concentration,
        "synergy_ratio": synergy_ratio,
        "role_balance": dict(role_counts),
    }
