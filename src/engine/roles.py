"""Card role classification for deck building."""
from __future__ import annotations

from src.database.models import Card

ROLE_DESCRIPTIONS: dict[str, str] = {
    "lands": "Mana-producing or mana-fixing lands.",
    "ramp": "Acceleration pieces that increase mana production or land count.",
    "draw": "Repeatable or burst card draw and card advantage.",
    "removal": "Targeted or mass removal, interaction, or disruption.",
    "wincons": "Primary finishers or explicit win conditions.",
    "synergy": "Theme enablers and commander-specific synergies.",
    "flex": "Utility slots that cover gaps not captured by other roles.",
}


def get_role_description(role: str) -> str:
    """Return a short description for a deck role."""
    return ROLE_DESCRIPTIONS.get(role, "General support for the deck plan.")


def classify_card_role(card: Card) -> str:
    """Classify a card into a deck role based on its properties.

    Uses pattern matching on oracle text and type line to determine
    the card's primary function in a Commander deck.

    Args:
        card: Card to classify

    Returns:
        Role name: "lands", "ramp", "draw", "removal", "wincons", "synergy", or "flex"
    """
    type_line = (card.type_line or "").lower()
    oracle_text = (card.oracle_text or "").lower()

    # Lands
    if "land" in type_line:
        return "lands"

    # Ramp (mana acceleration)
    if any(pattern in oracle_text for pattern in [
        "add {",
        "search your library for a land",
        "search your library for a basic land",
        "search your library for up to",
        "put a land card",
    ]):
        return "ramp"

    # Mana rocks (artifacts with low CMC that produce mana)
    if "artifact" in type_line and card.cmc <= 3 and "add {" in oracle_text:
        return "ramp"

    # Mana dorks (creatures that tap for mana)
    if "creature" in type_line and card.cmc <= 3 and "{t}: add {" in oracle_text:
        return "ramp"

    # Card draw
    if any(pattern in oracle_text for pattern in [
        "draw a card",
        "draw cards",
        "draw two cards",
        "draw three cards",
        "you draw",
        "target player draws",
    ]):
        # Exclude cantrips on creatures (likely synergy pieces)
        if "creature" in type_line and "enters" in oracle_text:
            pass  # Let it fall through to wincons/synergy check
        else:
            return "draw"

    # Removal
    if any(pattern in oracle_text for pattern in [
        "destroy target",
        "destroy all",
        "exile target",
        "exile all",
        "return target",
        "return all",
        "gets -",
        "put target",
        "sacrifice target",
        "sacrifice all",
    ]):
        return "removal"

    # Win conditions (high CMC threats or explicit win cards)
    if card.cmc >= 7:
        return "wincons"

    if any(pattern in oracle_text for pattern in [
        "you win the game",
        "target player loses the game",
        "each opponent loses",
    ]):
        return "wincons"

    # Big creatures
    if "creature" in type_line and card.cmc >= 6:
        return "wincons"

    # Synergy (commander-specific synergies, theme enablers)
    # This is the fallback category for cards that don't fit other roles
    # Future enhancement: match keywords/tribes from commander
    return "synergy"
