"""Tests for deck validator."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base, Card, Commander, Deck, DeckCard
from src.engine.validator import validate_deck


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def valid_commander(db_session: Session):
    """Create a valid commander for testing."""
    card = Card(
        scryfall_id="test-commander",
        name="Test Commander",
        type_line="Legendary Creature — Human Wizard",
        color_identity=["U", "R"],
        cmc=3.0,
        legalities={"commander": "legal"},
    )
    db_session.add(card)
    db_session.commit()

    commander = Commander(
        card_id=card.id,
        eligibility_reason="legendary creature",
        color_identity=["U", "R"],
    )
    db_session.add(commander)
    db_session.commit()

    return commander


def test_validate_deck_valid_100_cards(db_session: Session, valid_commander: Commander):
    """Test validation passes for a valid 100-card deck."""
    deck = Deck(commander_id=valid_commander.id, constraints={})
    db_session.add(deck)
    db_session.commit()

    # Add 100 legal cards (validator counts deck_cards, not including commander separately)
    for i in range(100):
        card = Card(
            scryfall_id=f"card-{i}",
            name=f"Card {i}",
            type_line="Instant",
            color_identity=["U"],
            cmc=2.0,
            legalities={"commander": "legal"},
        )
        db_session.add(card)
        db_session.commit()

        deck_card = DeckCard(deck_id=deck.id, card_id=card.id, quantity=1)
        db_session.add(deck_card)

    db_session.commit()

    is_valid, errors = validate_deck(deck)
    if not is_valid:
        print(f"Errors: {errors}")
    assert is_valid, f"Deck validation failed with errors: {errors}"
    assert len(errors) == 0


def test_validate_deck_too_few_cards(db_session: Session, valid_commander: Commander):
    """Test validation fails with fewer than 100 cards."""
    deck = Deck(commander_id=valid_commander.id, constraints={})
    db_session.add(deck)
    db_session.commit()

    # Add only 50 cards
    for i in range(50):
        card = Card(
            scryfall_id=f"card-{i}",
            name=f"Card {i}",
            type_line="Instant",
            color_identity=["U"],
            cmc=2.0,
            legalities={"commander": "legal"},
        )
        db_session.add(card)
        db_session.commit()

        deck_card = DeckCard(deck_id=deck.id, card_id=card.id, quantity=1)
        db_session.add(deck_card)

    db_session.commit()

    is_valid, errors = validate_deck(deck)
    assert not is_valid
    assert len(errors) > 0
    assert any("exactly 100 cards" in err.lower() for err in errors)
    assert any("50" in err for err in errors)


def test_validate_deck_too_many_cards(db_session: Session, valid_commander: Commander):
    """Test validation fails with more than 100 cards."""
    deck = Deck(commander_id=valid_commander.id, constraints={})
    db_session.add(deck)
    db_session.commit()

    # Add 105 cards
    for i in range(105):
        card = Card(
            scryfall_id=f"card-{i}",
            name=f"Card {i}",
            type_line="Instant",
            color_identity=["U"],
            cmc=2.0,
            legalities={"commander": "legal"},
        )
        db_session.add(card)
        db_session.commit()

        deck_card = DeckCard(deck_id=deck.id, card_id=card.id, quantity=1)
        db_session.add(deck_card)

    db_session.commit()

    is_valid, errors = validate_deck(deck)
    assert not is_valid
    assert any("exactly 100 cards" in err.lower() for err in errors)


def test_validate_deck_singleton_violation(db_session: Session, valid_commander: Commander):
    """Test validation fails when non-basic card has multiple copies."""
    deck = Deck(commander_id=valid_commander.id, constraints={})
    db_session.add(deck)
    db_session.commit()

    # Add a non-basic card with 2 copies
    card = Card(
        scryfall_id="lightning-bolt",
        name="Lightning Bolt",
        type_line="Instant",
        color_identity=["R"],
        cmc=1.0,
        legalities={"commander": "legal"},
    )
    db_session.add(card)
    db_session.commit()

    deck_card = DeckCard(deck_id=deck.id, card_id=card.id, quantity=2)
    db_session.add(deck_card)
    db_session.commit()

    is_valid, errors = validate_deck(deck)
    assert not is_valid
    assert any("Lightning Bolt" in err for err in errors)
    assert any("2 copies" in err for err in errors)


def test_validate_deck_basic_lands_allowed_multiple(db_session: Session, valid_commander: Commander):
    """Test validation allows multiple copies of basic lands."""
    deck = Deck(commander_id=valid_commander.id, constraints={})
    db_session.add(deck)
    db_session.commit()

    # Add 30 islands (basic lands)
    island = Card(
        scryfall_id="island",
        name="Island",
        type_line="Basic Land — Island",
        color_identity=["U"],
        cmc=0.0,
        legalities={"commander": "legal"},
    )
    db_session.add(island)
    db_session.commit()

    deck_card = DeckCard(deck_id=deck.id, card_id=island.id, quantity=30)
    db_session.add(deck_card)

    # Add 70 other cards to reach 100 total
    for i in range(70):
        card = Card(
            scryfall_id=f"card-{i}",
            name=f"Card {i}",
            type_line="Instant",
            color_identity=["U"],
            cmc=2.0,
            legalities={"commander": "legal"},
        )
        db_session.add(card)
        db_session.commit()

        dc = DeckCard(deck_id=deck.id, card_id=card.id, quantity=1)
        db_session.add(dc)

    db_session.commit()

    is_valid, errors = validate_deck(deck)
    # Should not complain about multiple Islands since they're basic
    assert not any("Island" in err for err in errors)


def test_validate_deck_color_identity_violation(db_session: Session, valid_commander: Commander):
    """Test validation fails when card is outside commander's color identity."""
    deck = Deck(commander_id=valid_commander.id, constraints={})
    db_session.add(deck)
    db_session.commit()

    # Commander is U/R, add a green card
    card = Card(
        scryfall_id="llanowar-elves",
        name="Llanowar Elves",
        type_line="Creature — Elf Druid",
        color_identity=["G"],
        cmc=1.0,
        legalities={"commander": "legal"},
    )
    db_session.add(card)
    db_session.commit()

    deck_card = DeckCard(deck_id=deck.id, card_id=card.id, quantity=1)
    db_session.add(deck_card)
    db_session.commit()

    is_valid, errors = validate_deck(deck)
    assert not is_valid
    assert any("Llanowar Elves" in err for err in errors)
    assert any("outside commander identity" in err.lower() for err in errors)


def test_validate_deck_illegal_card(db_session: Session, valid_commander: Commander):
    """Test validation fails when card is not commander-legal."""
    deck = Deck(commander_id=valid_commander.id, constraints={})
    db_session.add(deck)
    db_session.commit()

    # Add a banned card
    card = Card(
        scryfall_id="black-lotus",
        name="Black Lotus",
        type_line="Artifact",
        color_identity=[],
        cmc=0.0,
        legalities={"commander": "banned"},
    )
    db_session.add(card)
    db_session.commit()

    deck_card = DeckCard(deck_id=deck.id, card_id=card.id, quantity=1)
    db_session.add(deck_card)
    db_session.commit()

    is_valid, errors = validate_deck(deck)
    assert not is_valid
    assert any("Black Lotus" in err for err in errors)
    assert any("not legal" in err.lower() for err in errors)


def test_validate_deck_colorless_card_allowed(db_session: Session, valid_commander: Commander):
    """Test validation allows colorless cards in any deck."""
    deck = Deck(commander_id=valid_commander.id, constraints={})
    db_session.add(deck)
    db_session.commit()

    # Add a colorless artifact (should be allowed)
    card = Card(
        scryfall_id="sol-ring",
        name="Sol Ring",
        type_line="Artifact",
        color_identity=[],
        cmc=1.0,
        legalities={"commander": "legal"},
    )
    db_session.add(card)
    db_session.commit()

    deck_card = DeckCard(deck_id=deck.id, card_id=card.id, quantity=1)
    db_session.add(deck_card)
    db_session.commit()

    is_valid, errors = validate_deck(deck)
    # Colorless cards should not trigger color identity errors
    assert not any("Sol Ring" in err and "color" in err.lower() for err in errors)


def test_validate_deck_multiple_errors(db_session: Session, valid_commander: Commander):
    """Test validation returns all errors when multiple issues exist."""
    deck = Deck(commander_id=valid_commander.id, constraints={})
    db_session.add(deck)
    db_session.commit()

    # Add too few cards
    for i in range(10):
        card = Card(
            scryfall_id=f"card-{i}",
            name=f"Card {i}",
            type_line="Instant",
            color_identity=["U"],
            cmc=2.0,
            legalities={"commander": "legal"},
        )
        db_session.add(card)
        db_session.commit()

        deck_card = DeckCard(deck_id=deck.id, card_id=card.id, quantity=1)
        db_session.add(deck_card)

    # Add a color identity violation
    green_card = Card(
        scryfall_id="green-card",
        name="Green Card",
        type_line="Creature",
        color_identity=["G"],
        cmc=2.0,
        legalities={"commander": "legal"},
    )
    db_session.add(green_card)
    db_session.commit()

    deck_card = DeckCard(deck_id=deck.id, card_id=green_card.id, quantity=1)
    db_session.add(deck_card)
    db_session.commit()

    is_valid, errors = validate_deck(deck)
    assert not is_valid
    assert len(errors) >= 2  # At least card count and color identity errors


def test_validate_deck_empty_deck(db_session: Session, valid_commander: Commander):
    """Test validation fails for empty deck."""
    deck = Deck(commander_id=valid_commander.id, constraints={})
    db_session.add(deck)
    db_session.commit()

    is_valid, errors = validate_deck(deck)
    assert not is_valid
    assert any("0" in err for err in errors)
    assert len(errors) > 0


def test_validate_deck_error_message_format(db_session: Session, valid_commander: Commander):
    """Test that error messages have expected format."""
    deck = Deck(commander_id=valid_commander.id, constraints={})
    db_session.add(deck)
    db_session.commit()

    # Add too few cards to trigger count error
    card = Card(
        scryfall_id="test-msg",
        name="Test Card",
        type_line="Instant",
        color_identity=["U"],
        cmc=2.0,
        legalities={"commander": "legal"},
    )
    db_session.add(card)
    db_session.commit()

    deck_card = DeckCard(deck_id=deck.id, card_id=card.id, quantity=1)
    db_session.add(deck_card)
    db_session.commit()

    is_valid, errors = validate_deck(deck)
    assert not is_valid
    # Check the exact format of the error message
    assert any("Deck must have exactly 100 cards" in err for err in errors)
    assert any("has 1" in err for err in errors)


def test_validate_deck_singleton_error_message(db_session: Session, valid_commander: Commander):
    """Test singleton violation error message format."""
    deck = Deck(commander_id=valid_commander.id, constraints={})
    db_session.add(deck)
    db_session.commit()

    card = Card(
        scryfall_id="test-singleton-msg",
        name="Counterspell",
        type_line="Instant",
        color_identity=["U"],
        cmc=2.0,
        legalities={"commander": "legal"},
    )
    db_session.add(card)
    db_session.commit()

    deck_card = DeckCard(deck_id=deck.id, card_id=card.id, quantity=4)
    db_session.add(deck_card)
    db_session.commit()

    is_valid, errors = validate_deck(deck)
    assert not is_valid
    # Check exact error message format
    assert any("Non-basic card" in err for err in errors)
    assert any("Counterspell" in err for err in errors)
    assert any("4 copies" in err for err in errors)


def test_validate_deck_color_identity_error_message(db_session: Session, valid_commander: Commander):
    """Test color identity violation error message format."""
    deck = Deck(commander_id=valid_commander.id, constraints={})
    db_session.add(deck)
    db_session.commit()

    # Commander is U/R, add a green card
    card = Card(
        scryfall_id="test-color-msg",
        name="Rampant Growth",
        type_line="Sorcery",
        color_identity=["G"],
        cmc=2.0,
        legalities={"commander": "legal"},
    )
    db_session.add(card)
    db_session.commit()

    deck_card = DeckCard(deck_id=deck.id, card_id=card.id, quantity=1)
    db_session.add(deck_card)
    db_session.commit()

    is_valid, errors = validate_deck(deck)
    assert not is_valid
    # Check exact error message format
    assert any("Rampant Growth" in err for err in errors)
    assert any("outside commander identity" in err for err in errors)


def test_validate_deck_illegal_card_error_message(db_session: Session, valid_commander: Commander):
    """Test illegal card error message format."""
    deck = Deck(commander_id=valid_commander.id, constraints={})
    db_session.add(deck)
    db_session.commit()

    card = Card(
        scryfall_id="test-illegal-msg",
        name="Time Walk",
        type_line="Sorcery",
        color_identity=["U"],
        cmc=2.0,
        legalities={"commander": "banned"},
    )
    db_session.add(card)
    db_session.commit()

    deck_card = DeckCard(deck_id=deck.id, card_id=card.id, quantity=1)
    db_session.add(deck_card)
    db_session.commit()

    is_valid, errors = validate_deck(deck)
    assert not is_valid
    # Check exact error message format
    assert any("Time Walk" in err for err in errors)
    assert any("not legal in Commander format" in err for err in errors)


def test_validate_deck_card_count_accumulation(db_session: Session, valid_commander: Commander):
    """Test that card quantities are accumulated correctly with +=."""
    deck = Deck(commander_id=valid_commander.id, constraints={})
    db_session.add(deck)
    db_session.commit()

    # Commander is U/R, so use Island (basic land, colorless in color identity)
    card = Card(
        scryfall_id="test-accumulate",
        name="Island",
        type_line="Basic Land — Island",
        color_identity=[],  # Basic lands are colorless
        cmc=0.0,
        legalities={"commander": "legal"},
    )
    db_session.add(card)
    db_session.commit()

    # Add same card multiple times (simulating multiple deck_card entries with same card_id)
    # This tests that += is used, not = or -=
    deck_card1 = DeckCard(deck_id=deck.id, card_id=card.id, quantity=20)
    deck_card2 = DeckCard(deck_id=deck.id, card_id=card.id, quantity=15)
    db_session.add(deck_card1)
    db_session.add(deck_card2)
    db_session.commit()

    # Add 65 more cards to reach 100 total (use U and R colors to match commander)
    for i in range(65):
        other_card = Card(
            scryfall_id=f"card-accum-{i}",
            name=f"Card {i}",
            type_line="Instant",
            color_identity=["U"] if i % 2 == 0 else ["R"],  # Alternate between U and R
            cmc=2.0,
            legalities={"commander": "legal"},
        )
        db_session.add(other_card)
        db_session.commit()

        dc = DeckCard(deck_id=deck.id, card_id=other_card.id, quantity=1)
        db_session.add(dc)

    db_session.commit()

    is_valid, errors = validate_deck(deck)
    # Should be valid - 20+15+65 = 100 cards, and Island is a basic land
    assert is_valid, f"Expected valid deck but got errors: {errors}"
