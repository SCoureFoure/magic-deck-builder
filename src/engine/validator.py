"""Deck validation for Commander format."""
from __future__ import annotations

from collections import Counter

from src.database.models import Deck


def validate_deck(deck: Deck) -> tuple[bool, list[str]]:
    """Validate a Commander deck for format legality.

    Checks:
    - Exactly 100 cards (including commander)
    - Singleton (max 1 copy except basic lands)
    - Color identity compliance
    - All cards commander-legal

    Args:
        deck: Deck to validate

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors: list[str] = []

    # Count total cards
    total_cards = sum(dc.quantity for dc in deck.deck_cards)

    if total_cards != 100:
        errors.append(f"Deck must have exactly 100 cards, has {total_cards}")

    # Check singleton (except basics)
    card_counts: Counter[int] = Counter()
    for deck_card in deck.deck_cards:
        card = deck_card.card
        card_counts[card.id] += deck_card.quantity

        # Singleton check (except basic lands)
        if deck_card.quantity > 1:
            is_basic = card.type_line and "basic" in card.type_line.lower()
            if not is_basic:
                errors.append(
                    f"Non-basic card '{card.name}' has {deck_card.quantity} copies"
                )

    # Check color identity
    commander_colors = set(deck.commander.color_identity or [])

    for deck_card in deck.deck_cards:
        card = deck_card.card
        card_colors = set(card.color_identity or [])

        if not card_colors.issubset(commander_colors):
            errors.append(
                f"Card '{card.name}' ({card_colors}) outside commander identity ({commander_colors})"
            )

    # Check commander legality for all cards
    for deck_card in deck.deck_cards:
        card = deck_card.card
        if card.legalities.get("commander") != "legal":
            errors.append(f"Card '{card.name}' is not legal in Commander format")

    is_valid = len(errors) == 0
    return is_valid, errors
