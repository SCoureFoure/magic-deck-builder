"""Archetype taxonomy and deterministic tagger for deck identity."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.database.models import Card


@dataclass(frozen=True)
class ArchetypeDefinition:
    """Definition for an archetype and its simple pattern matches."""

    name: str
    description: str
    weight: float
    text_patterns: tuple[str, ...] = ()
    type_patterns: tuple[str, ...] = ()
    name_patterns: tuple[str, ...] = ()


ARCHETYPES: tuple[ArchetypeDefinition, ...] = (
    ArchetypeDefinition(
        name="voltron",
        description="Commander damage, protection, evasion, auras/equipment.",
        weight=0.6,
        text_patterns=(
            "commander damage",
            "double strike",
            "hexproof",
            "indestructible",
            "protection from",
            "enchanted creature gets",
            "equipped creature",
            "attach",
        ),
        type_patterns=("aura", "equipment"),
    ),
    ArchetypeDefinition(
        name="equipment",
        description="Equipment-focused strategy.",
        weight=0.7,
        text_patterns=("equip", "equipped creature"),
        type_patterns=("equipment",),
    ),
    ArchetypeDefinition(
        name="spellslinger",
        description="Instants/sorceries matter, copy, storm.",
        weight=0.6,
        text_patterns=("when you cast", "copy target", "magecraft", "storm"),
        type_patterns=("instant", "sorcery"),
    ),
    ArchetypeDefinition(
        name="aristocrats",
        description="Sacrifice and death triggers.",
        weight=0.6,
        text_patterns=("sacrifice a creature", "when a creature dies", "dies"),
        name_patterns=("blood artist", "zulaport"),
    ),
    ArchetypeDefinition(
        name="tribal",
        description="Creature type synergies and lords.",
        weight=0.5,
        text_patterns=(
            "choose a creature type",
            "creature type",
            "other creatures you control",
            "creatures you control get",
        ),
        type_patterns=("tribal",),
    ),
    ArchetypeDefinition(
        name="tokens",
        description="Token generation and go-wide payoffs.",
        weight=0.6,
        text_patterns=("create a", "token", "populate"),
    ),
    ArchetypeDefinition(
        name="control",
        description="Reactive answers and permission.",
        weight=0.5,
        text_patterns=("counter target", "destroy all", "exile all"),
    ),
    ArchetypeDefinition(
        name="combo",
        description="Tutor and combo-enabling pieces.",
        weight=0.4,
        text_patterns=("search your library", "tutor", "untap all"),
    ),
    ArchetypeDefinition(
        name="reanimator",
        description="Graveyard recursion.",
        weight=0.6,
        text_patterns=(
            "return target creature card from your graveyard",
            "return target creature card from a graveyard",
            "reanimate",
        ),
    ),
    ArchetypeDefinition(
        name="stax",
        description="Tax and resource denial.",
        weight=0.6,
        text_patterns=("players can't", "can't untap", "unless they pay"),
    ),
    ArchetypeDefinition(
        name="landfall",
        description="Land-based triggers and extra land drops.",
        weight=0.6,
        text_patterns=("landfall", "whenever a land enters", "play an additional land"),
    ),
    ArchetypeDefinition(
        name="plus1_counters",
        description="+1/+1 counter synergies.",
        weight=0.6,
        text_patterns=("+1/+1 counter", "proliferate"),
    ),
    ArchetypeDefinition(
        name="enchantress",
        description="Enchantment-focused value.",
        weight=0.6,
        text_patterns=("constellation", "enchantment"),
        type_patterns=("enchantment",),
    ),
    ArchetypeDefinition(
        name="wheels",
        description="Hand refills and wheel effects.",
        weight=0.6,
        text_patterns=("discard your hand", "draw seven", "each player discards"),
    ),
)


def _count_matches(text: str, patterns: Iterable[str]) -> int:
    return sum(1 for pattern in patterns if pattern in text)


def extract_archetype_tags(card: Card) -> dict[str, float]:
    """Extract archetype weights for a card using pattern matches."""
    oracle_text = (card.oracle_text or "").lower()
    type_line = (card.type_line or "").lower()
    name = (card.name or "").lower()

    tags: dict[str, float] = {}

    for archetype in ARCHETYPES:
        matches = 0
        if archetype.text_patterns:
            matches += _count_matches(oracle_text, archetype.text_patterns)
        if archetype.type_patterns:
            matches += _count_matches(type_line, archetype.type_patterns)
        if archetype.name_patterns:
            matches += _count_matches(name, archetype.name_patterns)

        if matches > 0:
            tags[archetype.name] = min(1.0, archetype.weight * matches)

    return tags


def extract_identity(commander: Card, seeds: list[Card]) -> dict[str, float]:
    """Build initial identity from commander + seed cards."""
    identity: dict[str, float] = {}
    for card in [commander, *seeds]:
        tags = extract_archetype_tags(card)
        for archetype, weight in tags.items():
            identity[archetype] = max(identity.get(archetype, 0.0), weight)

    if not identity:
        return {}

    max_weight = max(identity.values())
    if max_weight <= 0:
        return {}

    return {archetype: weight / max_weight for archetype, weight in identity.items()}


def update_identity(identity: dict[str, float], card: Card, alpha: float = 0.1) -> dict[str, float]:
    """Blend a card's archetype tags into the identity vector."""
    if alpha <= 0:
        return identity

    tags = extract_archetype_tags(card)
    if not tags:
        return identity

    updated: dict[str, float] = dict(identity)
    for archetype in set(updated.keys()) | set(tags.keys()):
        current = updated.get(archetype, 0.0)
        incoming = tags.get(archetype, 0.0)
        updated[archetype] = current * (1 - alpha) + incoming * alpha

    return updated


def compute_identity_from_deck(commander: Card, cards: Iterable[Card]) -> dict[str, float]:
    """Compute identity by iteratively blending deck cards into commander identity."""
    identity = extract_identity(commander, [])
    for card in cards:
        identity = update_identity(identity, card, alpha=0.1)
    return identity


def score_card_for_identity(card: Card, identity: dict[str, float]) -> float:
    """Score a card by how well it matches the identity weights."""
    if not identity:
        return 0.0
    weight_sum = sum(identity.values())
    if weight_sum <= 0:
        return 0.0

    tags = extract_archetype_tags(card)
    score = sum(tags.get(arch, 0.0) * weight for arch, weight in identity.items())
    return score / weight_sum
