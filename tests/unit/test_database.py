"""Tests for database models."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Archetype, Base, Card, Commander, Deck, DeckCard, Role


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def test_create_card(db_session: Session):
    """Test creating a card."""
    card = Card(
        scryfall_id="12345678-1234-1234-1234-123456789012",
        name="Sol Ring",
        type_line="Artifact",
        oracle_text="Add two colorless mana.",
        colors=[],
        color_identity=[],
        mana_cost="{1}",
        cmc=1.0,
        legalities={"commander": "legal"},
        price_usd=1.5,
    )
    db_session.add(card)
    db_session.commit()

    # Query it back
    result = db_session.query(Card).filter_by(name="Sol Ring").first()
    assert result is not None
    assert result.name == "Sol Ring"
    assert result.cmc == 1.0
    assert result.scryfall_id == "12345678-1234-1234-1234-123456789012"


def test_create_commander(db_session: Session):
    """Test creating a commander."""
    # First create a card
    card = Card(
        scryfall_id="atraxa-praetors-voice",
        name="Atraxa, Praetors' Voice",
        type_line="Legendary Creature — Phyrexian Angel Horror",
        oracle_text="Flying, vigilance, deathtouch, lifelink",
        colors=["W", "U", "B", "G"],
        color_identity=["W", "U", "B", "G"],
        mana_cost="{G}{W}{U}{B}",
        cmc=4.0,
        legalities={"commander": "legal"},
    )
    db_session.add(card)
    db_session.commit()

    # Create commander
    commander = Commander(
        card_id=card.id,
        eligibility_reason="legendary creature",
        color_identity=["W", "U", "B", "G"],
    )
    db_session.add(commander)
    db_session.commit()

    # Query it back
    result = db_session.query(Commander).first()
    assert result is not None
    assert result.card.name == "Atraxa, Praetors' Voice"
    assert result.eligibility_reason == "legendary creature"


def test_commander_one_to_one_relationship(db_session: Session):
    """Test that commander_info is a single object, not a list."""
    card = Card(
        scryfall_id="test-commander",
        name="Test Commander",
        type_line="Legendary Creature",
        color_identity=["R"],
        cmc=3.0,
        legalities={"commander": "legal"},
    )
    db_session.add(card)
    db_session.commit()

    commander = Commander(
        card_id=card.id, eligibility_reason="legendary creature", color_identity=["R"]
    )
    db_session.add(commander)
    db_session.commit()

    # Access backref
    refreshed_card = db_session.query(Card).filter_by(name="Test Commander").first()
    # Should be a single object, not a list
    assert refreshed_card.commander_info is not None
    assert isinstance(refreshed_card.commander_info, Commander)
    assert refreshed_card.commander_info.eligibility_reason == "legendary creature"


def test_create_role(db_session: Session):
    """Test creating a role."""
    role = Role(name="ramp", description="Cards that accelerate mana production")
    db_session.add(role)
    db_session.commit()

    result = db_session.query(Role).filter_by(name="ramp").first()
    assert result is not None
    assert result.name == "ramp"


def test_create_archetype(db_session: Session):
    """Test creating an archetype."""
    archetype = Archetype(name="tribal", description="Creature type matters")
    db_session.add(archetype)
    db_session.commit()

    result = db_session.query(Archetype).filter_by(name="tribal").first()
    assert result is not None
    assert result.name == "tribal"


def test_card_unique_scryfall_id(db_session: Session):
    """Test that scryfall_id is unique."""
    card1 = Card(
        scryfall_id="same-id",
        name="Card 1",
        type_line="Creature",
        color_identity=[],
        cmc=1.0,
        legalities={},
    )
    card2 = Card(
        scryfall_id="same-id",
        name="Card 2",
        type_line="Creature",
        color_identity=[],
        cmc=2.0,
        legalities={},
    )

    db_session.add(card1)
    db_session.commit()

    db_session.add(card2)
    with pytest.raises(Exception):  # Will be IntegrityError
        db_session.commit()
