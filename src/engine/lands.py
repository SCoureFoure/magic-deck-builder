"""Land calculation for Commander decks."""
from __future__ import annotations


def calculate_land_distribution(
    color_identity: list[str], total_lands: int = 37
) -> dict[str, int]:
    """Calculate basic land distribution for a Commander deck.

    Based on Riftgate MTG Land Calculator methodology:
    https://riftgate.com/pages/mtg-land-calculator

    For MVP, uses equal distribution across colors. Future enhancement
    would weight by color pip requirements in mana costs.

    Args:
        color_identity: List of color letters (e.g., ["W", "U", "B"])
        total_lands: Total lands to distribute (default 37 for Commander)

    Returns:
        Dictionary mapping color to land count (e.g., {"W": 12, "U": 13, "B": 12})
        For multicolor, reserves 1 slot for Command Tower (returned separately)
    """
    if not color_identity:
        # Colorless commander - all basics (Wastes)
        return {"C": total_lands}

    num_colors = len(color_identity)

    if num_colors == 1:
        # Monocolor - all basics of that color
        return {color_identity[0]: total_lands}

    # Multicolor - reserve 1 for Command Tower, distribute rest equally
    basics_count = total_lands - 1  # Reserve 1 for Command Tower
    lands_per_color = basics_count // num_colors
    remainder = basics_count % num_colors

    distribution: dict[str, int] = {}
    for i, color in enumerate(sorted(color_identity)):
        # Distribute remainder to first N colors alphabetically
        distribution[color] = lands_per_color + (1 if i < remainder else 0)

    return distribution


def needs_command_tower(color_identity: list[str]) -> bool:
    """Check if deck should include Command Tower.

    Args:
        color_identity: List of color letters

    Returns:
        True if multicolor (2+ colors), False otherwise
    """
    return len(color_identity) > 1
