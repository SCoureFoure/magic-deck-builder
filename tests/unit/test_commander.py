"""Tests for commander eligibility and utilities."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base, Card, Commander
from src.engine.commander import (
    create_commander_entry,
    find_commanders,
    is_commander_eligible,
    populate_commanders,
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def test_is_commander_eligible_legendary_creature():
    """Test that legendary creatures are commander eligible."""
    card = Card(
        scryfall_id="test-1",
        name="Test Commander",
        type_line="Legendary Creature — Human",
        color_identity=["W"],
        cmc=3.0,
        legalities={"commander": "legal"},
    )

    is_eligible, reason = is_commander_eligible(card)
    assert is_eligible is True
    assert reason == "legendary creature"


def test_is_commander_eligible_can_be_your_commander():
    """Test cards with 'can be your commander' text."""
    card = Card(
        scryfall_id="test-2",
        name="Test Planeswalker",
        type_line="Legendary Planeswalker",
        oracle_text="Can be your commander.\n+1: Draw a card.",
        color_identity=["U"],
        cmc=4.0,
        legalities={"commander": "legal"},
    )

    is_eligible, reason = is_commander_eligible(card)
    assert is_eligible is True
    assert reason == "can be your commander"


def test_is_commander_eligible_partner():
    """Test cards with partner ability.

    Note: Legendary creatures are detected first, so this will return
    'legendary creature' rather than 'partner' (which is also valid).
    """
    card = Card(
        scryfall_id="test-3",
        name="Test Partner",
        type_line="Legendary Creature — Human Warrior",
        oracle_text="Partner (You can have two commanders if both have partner.)",
        color_identity=["R"],
        cmc=3.0,
        legalities={"commander": "legal"},
    )

    is_eligible, reason = is_commander_eligible(card)
    assert is_eligible is True
    # Legendary creatures are detected first, so reason will be "legendary creature"
    assert reason == "legendary creature"


def test_is_commander_eligible_background():
    """Test background enchantments."""
    card = Card(
        scryfall_id="test-4",
        name="Test Background",
        type_line="Legendary Enchantment — Background",
        oracle_text="Commander creatures you own get +1/+1.",
        color_identity=["B"],
        cmc=2.0,
        legalities={"commander": "legal"},
    )

    is_eligible, reason = is_commander_eligible(card)
    assert is_eligible is True
    assert reason == "background"


def test_is_commander_not_eligible():
    """Test non-commander cards."""
    card = Card(
        scryfall_id="test-5",
        name="Sol Ring",
        type_line="Artifact",
        oracle_text="{T}: Add {C}{C}.",
        color_identity=[],
        cmc=1.0,
        legalities={"commander": "legal"},
    )

    is_eligible, reason = is_commander_eligible(card)
    assert is_eligible is False
    assert reason is None


def test_is_commander_not_legal():
    """Test commander-illegal cards."""
    card = Card(
        scryfall_id="test-6",
        name="Banned Commander",
        type_line="Legendary Creature — Elder Dragon",
        color_identity=["U", "B", "R"],
        cmc=7.0,
        legalities={"commander": "banned"},
    )

    is_eligible, reason = is_commander_eligible(card)
    assert is_eligible is False
    assert reason is None


def test_find_commanders(db_session: Session):
    """Test finding commanders by name."""
    # Add test cards
    commander = Card(
        scryfall_id="cmd-1",
        name="Atraxa, Praetors' Voice",
        type_line="Legendary Creature — Phyrexian Angel",
        oracle_text="Flying, vigilance, deathtouch, lifelink",
        color_identity=["W", "U", "B", "G"],
        cmc=4.0,
        legalities={"commander": "legal"},
    )

    non_commander = Card(
        scryfall_id="nc-1",
        name="Lightning Bolt",
        type_line="Instant",
        oracle_text="Deal 3 damage to any target.",
        color_identity=["R"],
        cmc=1.0,
        legalities={"commander": "legal"},
    )

    db_session.add_all([commander, non_commander])
    db_session.commit()

    # Search for commanders
    results = find_commanders(db_session, name_query="Atraxa")
    assert len(results) == 1
    assert results[0].name == "Atraxa, Praetors' Voice"

    # Search for non-commander should return nothing
    results = find_commanders(db_session, name_query="Lightning")
    assert len(results) == 0


def test_create_commander_entry(db_session: Session):
    """Test creating commander database entries."""
    card = Card(
        scryfall_id="cmd-2",
        name="Urza, Lord High Artificer",
        type_line="Legendary Creature — Human Artificer",
        oracle_text="When Urza enters the battlefield...",
        color_identity=["U"],
        cmc=4.0,
        legalities={"commander": "legal"},
    )
    db_session.add(card)
    db_session.commit()

    # Create commander entry
    commander = create_commander_entry(db_session, card)

    assert commander is not None
    assert commander.card_id == card.id
    assert commander.eligibility_reason == "legendary creature"
    assert commander.color_identity == ["U"]


def test_create_commander_entry_duplicate(db_session: Session):
    """Test that duplicate commander entries aren't created."""
    card = Card(
        scryfall_id="cmd-3",
        name="Test Commander",
        type_line="Legendary Creature — Human",
        color_identity=["W"],
        cmc=3.0,
        legalities={"commander": "legal"},
    )
    db_session.add(card)
    db_session.commit()

    # Create first entry
    commander1 = create_commander_entry(db_session, card)
    db_session.commit()

    # Try to create duplicate
    commander2 = create_commander_entry(db_session, card)

    assert commander1.id == commander2.id
    assert db_session.query(Commander).count() == 1


def test_populate_commanders(db_session: Session):
    """Test populating commanders table."""
    # Add multiple cards
    cards = [
        Card(
            scryfall_id=f"cmd-{i}",
            name=f"Commander {i}",
            type_line="Legendary Creature — Human",
            color_identity=["R"],
            cmc=3.0,
            legalities={"commander": "legal"},
        )
        for i in range(3)
    ]

    # Add non-commander
    cards.append(
        Card(
            scryfall_id="nc-1",
            name="Not a Commander",
            type_line="Artifact",
            color_identity=[],
            cmc=1.0,
            legalities={"commander": "legal"},
        )
    )

    db_session.add_all(cards)
    db_session.commit()

    # Populate commanders
    count = populate_commanders(db_session)

    assert count == 3  # Only the 3 legendary creatures
    assert db_session.query(Commander).count() == 3
