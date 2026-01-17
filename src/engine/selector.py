"""Card selection for deck building."""
from __future__ import annotations

import random
from typing import Optional

from sqlalchemy.orm import Session

from src.database.models import Card
from src.engine.archetypes import score_card_for_identity
from src.engine.roles import classify_card_role


def select_cards_for_role(
    session: Session,
    role: str,
    color_identity: list[str],
    count: int,
    identity: Optional[dict[str, float]] = None,
    exclude_ids: Optional[set[int]] = None,
) -> list[Card]:
    """Select cards for a specific role matching color identity.

    Args:
        session: Database session
        role: Role name to select for
        color_identity: Commander's color identity to match
        count: Target number of cards to select
        exclude_ids: Set of card IDs to exclude (e.g., already selected)

    Returns:
        List of selected cards (may be fewer than count if insufficient eligible cards)
    """
    exclude_ids = exclude_ids or set()

    # Query all cards (filter for legality in Python for SQLite compatibility)
    # Apply filters before limit
    query = session.query(Card)
    if exclude_ids:
        query = query.filter(Card.id.notin_(exclude_ids))
    query = query.limit(5000)  # Sample from first 5k cards for MVP

    # Filter by color identity: card's identity must be subset of commander's
    # For MVP: cards with no color identity (colorless) or matching colors
    eligible_cards: list[Card] = []

    for card in query.all():
        # Check commander legality
        if card.legalities.get("commander") != "legal":
            continue
        card_colors = set(card.color_identity or [])
        commander_colors = set(color_identity)

        # Card must not have colors outside commander's identity
        if card_colors.issubset(commander_colors):
            # Classify and check if it matches the role we want
            card_role = classify_card_role(card)
            if card_role == role:
                eligible_cards.append(card)

                # Early exit if we have enough candidates
                if len(eligible_cards) >= count * 3:  # Get 3x more than needed for variety
                    break

    if identity is not None:
        scored_cards = [
            (score_card_for_identity(card, identity), card) for card in eligible_cards
        ]
        scored_cards.sort(key=lambda item: (-item[0], item[1].name))
        return [card for _, card in scored_cards[:count]]

    # Randomly select up to 'count' cards
    return random.sample(eligible_cards, min(count, len(eligible_cards)))


def select_basic_lands(
    session: Session, land_distribution: dict[str, int]
) -> list[Card]:
    """Select basic land cards based on distribution.

    Args:
        session: Database session
        land_distribution: Map of color to count (e.g., {"W": 12, "U": 13})

    Returns:
        List of basic land cards
    """
    basic_names = {
        "W": "Plains",
        "U": "Island",
        "B": "Swamp",
        "R": "Mountain",
        "G": "Forest",
        "C": "Wastes",
    }

    lands: list[Card] = []

    for color, count in land_distribution.items():
        basic_name = basic_names.get(color)
        if not basic_name:
            continue

        # Query for the basic land
        basic = (
            session.query(Card)
            .filter(Card.name == basic_name, Card.type_line.ilike("%basic%"))
            .first()
        )

        if basic:
            # Add 'count' copies (we'll handle quantity in DeckCard)
            for _ in range(count):
                lands.append(basic)

    return lands


def select_command_tower(session: Session) -> Optional[Card]:
    """Select Command Tower card.

    Args:
        session: Database session

    Returns:
        Command Tower card or None if not found
    """
    return session.query(Card).filter(Card.name == "Command Tower").first()
