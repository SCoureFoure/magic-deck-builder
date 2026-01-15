"""Commander eligibility and utilities."""
import re
from typing import Optional

from sqlalchemy.orm import Session

from src.database.models import Card, Commander


def is_commander_eligible(card: Card) -> tuple[bool, Optional[str]]:
    """Check if a card can be a commander.

    Returns:
        Tuple of (is_eligible, reason)
        - is_eligible: True if card can be a commander
        - reason: String explaining why (e.g., "legendary creature", "has partner")
    """
    # Must be Commander legal
    if card.legalities.get("commander") != "legal":
        return False, None

    type_line_lower = card.type_line.lower()

    # Check if it's a legendary creature
    if "legendary" in type_line_lower and "creature" in type_line_lower:
        return True, "legendary creature"

    # Check for "can be your commander" text
    if card.oracle_text:
        oracle_lower = card.oracle_text.lower()
        if "can be your commander" in oracle_lower:
            return True, "can be your commander"

        # Check for planeswalkers with commander ability
        if "can be your commander" in oracle_lower and "planeswalker" in type_line_lower:
            return True, "planeswalker commander"

    # Check for Partner abilities
    if card.oracle_text:
        oracle_lower = card.oracle_text.lower()

        # Partner
        if re.search(r'\bpartner\b(?!\s+with)', oracle_lower):
            return True, "partner"

        # Partner with [name]
        if "partner with" in oracle_lower:
            return True, "partner with"

        # Friends forever
        if "friends forever" in oracle_lower:
            return True, "friends forever"

        # Choose a Background
        if "choose a background" in oracle_lower:
            return True, "choose a background"

    # Background cards (enchantments that can be commanders with "Choose a Background")
    if "background" in type_line_lower and "enchantment" in type_line_lower:
        return True, "background"

    return False, None


def find_commanders(
    session: Session, name_query: Optional[str] = None, limit: int = 10
) -> list[Card]:
    """Find cards that can be commanders.

    Args:
        session: Database session
        name_query: Optional name to search for (case-insensitive, partial match)
        limit: Maximum number of results to return

    Returns:
        List of Card objects that can be commanders
    """
    # Get all cards (filter legality in Python for SQLite compatibility)
    query = session.query(Card)

    if name_query:
        query = query.filter(Card.name.ilike(f"%{name_query}%"))

    # Filter for commander-eligible cards
    # Legendary creatures
    legendary_creatures = query.filter(
        Card.type_line.ilike("%legendary%"), Card.type_line.ilike("%creature%")
    )

    # Cards with "can be your commander" text
    can_be_commander = query.filter(Card.oracle_text.ilike("%can be your commander%"))

    # Combine results
    all_cards = legendary_creatures.union(can_be_commander).limit(limit * 2).all()

    # Filter for commander legality in Python (SQLite-compatible)
    results = [
        card
        for card in all_cards
        if card.legalities.get("commander") == "legal"
    ]

    unique: list[Card] = []
    seen: set[str] = set()
    for card in results:
        normalized_name = card.name.strip().lower()
        if normalized_name in seen:
            continue
        seen.add(normalized_name)
        unique.append(card)
        if len(unique) >= limit:
            break

    return unique


def create_commander_entry(session: Session, card: Card) -> Optional[Commander]:
    """Create a Commander database entry for a card.

    Args:
        session: Database session
        card: Card to create commander entry for

    Returns:
        Commander object if eligible, None otherwise
    """
    is_eligible, reason = is_commander_eligible(card)

    if not is_eligible or not reason:
        return None

    # Check if already exists
    existing = session.query(Commander).filter_by(card_id=card.id).first()
    if existing:
        return existing

    commander = Commander(
        card_id=card.id,
        eligibility_reason=reason,
        color_identity=card.color_identity,
    )
    session.add(commander)
    return commander


def populate_commanders(session: Session) -> int:
    """Populate the commanders table with all eligible cards.

    Args:
        session: Database session

    Returns:
        Number of commanders added
    """
    # Get all cards and filter in Python for SQLite compatibility
    all_cards = session.query(Card).all()

    count = 0
    for card in all_cards:
        # Check if commander legal
        if card.legalities.get("commander") != "legal":
            continue

        if create_commander_entry(session, card):
            count += 1
            if count % 100 == 0:
                session.commit()

    session.commit()
    return count
