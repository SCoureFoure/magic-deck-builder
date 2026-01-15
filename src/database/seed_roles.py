"""Seed the roles table with predefined card roles."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.database.engine import get_db
from src.database.models import Role


def seed_roles(session: Session) -> int:
    """Seed the roles table with standard EDH deck roles.

    Args:
        session: Database session

    Returns:
        Number of roles created (0 if already seeded)
    """
    roles_data = [
        {
            "name": "lands",
            "description": "Mana-producing lands including basics and Command Tower",
        },
        {
            "name": "ramp",
            "description": "Mana acceleration cards (rocks, dorks, land ramp)",
        },
        {
            "name": "draw",
            "description": "Card draw and card advantage engines",
        },
        {
            "name": "removal",
            "description": "Spot removal, board wipes, and interaction",
        },
        {
            "name": "synergy",
            "description": "Cards that synergize with commander strategy",
        },
        {
            "name": "wincons",
            "description": "Win conditions and game-ending threats",
        },
        {
            "name": "flex",
            "description": "Utility and meta-dependent flex slots",
        },
    ]

    existing_roles = session.query(Role).count()
    if existing_roles > 0:
        return 0

    created = 0
    for role_data in roles_data:
        role = Role(**role_data)
        session.add(role)
        created += 1

    session.commit()
    return created


def main() -> None:
    """CLI entry point for seeding roles."""
    with get_db() as db:
        count = seed_roles(db)
        if count > 0:
            print(f"✓ Created {count} roles")
        else:
            print("✓ Roles already seeded")


if __name__ == "__main__":
    main()
