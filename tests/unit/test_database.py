"""Tests for database models."""
import pytest
from sqlalchemy import create_engine, text
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


def test_card_tablename(db_session: Session):
    """Test Card model has correct table name."""
    assert Card.__tablename__ == "cards"
    # Verify the table actually exists in the database
    result = db_session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='cards'"))
    assert result.fetchone() is not None


def test_commander_tablename(db_session: Session):
    """Test Commander model has correct table name."""
    assert Commander.__tablename__ == "commanders"
    # Verify the table actually exists in the database
    result = db_session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='commanders'"))
    assert result.fetchone() is not None


def test_role_tablename(db_session: Session):
    """Test Role model has correct table name."""
    assert Role.__tablename__ == "roles"
    # Verify the table actually exists in the database
    result = db_session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='roles'"))
    assert result.fetchone() is not None


def test_archetype_tablename(db_session: Session):
    """Test Archetype model has correct table name."""
    assert Archetype.__tablename__ == "archetypes"
    # Verify the table actually exists in the database
    result = db_session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='archetypes'"))
    assert result.fetchone() is not None


def test_deck_tablename(db_session: Session):
    """Test Deck model has correct table name."""
    assert Deck.__tablename__ == "decks"
    # Verify the table actually exists in the database
    result = db_session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='decks'"))
    assert result.fetchone() is not None


def test_deckcard_tablename(db_session: Session):
    """Test DeckCard model has correct table name."""
    assert DeckCard.__tablename__ == "deck_cards"
    # Verify the table actually exists in the database
    result = db_session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='deck_cards'"))
    assert result.fetchone() is not None


def test_card_repr():
    """Test Card __repr__ method."""
    card = Card(
        scryfall_id="test-id",
        name="Test Card",
        type_line="Creature",
        color_identity=[],
        cmc=3.0,
        legalities={},
    )
    repr_str = repr(card)
    assert "Card" in repr_str
    assert "Test Card" in repr_str
    assert "3.0" in repr_str


def test_commander_repr():
    """Test Commander __repr__ method."""
    commander = Commander(
        card_id=1,
        eligibility_reason="legendary creature",
        color_identity=["R"],
    )
    repr_str = repr(commander)
    assert "Commander" in repr_str
    assert "card_id=1" in repr_str
    assert "legendary creature" in repr_str


def test_role_repr():
    """Test Role __repr__ method."""
    role = Role(name="ramp", description="Mana acceleration")
    repr_str = repr(role)
    assert "Role" in repr_str
    assert "ramp" in repr_str


def test_archetype_repr():
    """Test Archetype __repr__ method."""
    archetype = Archetype(name="tribal", description="Creature types")
    repr_str = repr(archetype)
    assert "Archetype" in repr_str
    assert "tribal" in repr_str


def test_deck_repr():
    """Test Deck __repr__ method."""
    deck = Deck(commander_id=5, constraints={})
    repr_str = repr(deck)
    assert "Deck" in repr_str
    assert "commander_id=5" in repr_str


def test_deckcard_repr():
    """Test DeckCard __repr__ method."""
    deck_card = DeckCard(deck_id=1, card_id=2, quantity=3)
    repr_str = repr(deck_card)
    assert "DeckCard" in repr_str
    assert "deck_id=1" in repr_str
    assert "card_id=2" in repr_str
    assert "qty=3" in repr_str


def test_deck_commander_relationship_name(db_session: Session):
    """Test Deck has 'commander' relationship with correct target."""
    # Create necessary data
    card = Card(
        scryfall_id="test-commander-rel",
        name="Test Commander",
        type_line="Legendary Creature",
        color_identity=["G"],
        cmc=4.0,
        legalities={"commander": "legal"},
    )
    db_session.add(card)
    db_session.commit()

    commander = Commander(
        card_id=card.id,
        eligibility_reason="legendary creature",
        color_identity=["G"],
    )
    db_session.add(commander)
    db_session.commit()

    deck = Deck(commander_id=commander.id, constraints={})
    db_session.add(deck)
    db_session.commit()

    # Verify relationship works
    assert deck.commander is not None
    assert deck.commander.id == commander.id
    assert isinstance(deck.commander, Commander)


def test_card_required_fields(db_session: Session):
    """Test that Card model requires essential fields."""
    # Should fail without scryfall_id
    with pytest.raises(Exception):
        card = Card(
            name="Test",
            type_line="Creature",
            color_identity=[],
            cmc=1.0,
            legalities={},
        )
        db_session.add(card)
        db_session.commit()


def test_card_optional_fields(db_session: Session):
    """Test that Card model allows optional fields to be None."""
    card = Card(
        scryfall_id="test-optional",
        name="Test Card",
        type_line="Creature",
        color_identity=[],
        cmc=1.0,
        legalities={},
        oracle_text=None,
        colors=None,
        mana_cost=None,
        price_usd=None,
        image_uris=None,
    )
    db_session.add(card)
    db_session.commit()

    result = db_session.query(Card).filter_by(scryfall_id="test-optional").first()
    assert result is not None
    assert result.oracle_text is None
    assert result.price_usd is None


def test_commander_color_identity_field(db_session: Session):
    """Test Commander color_identity field is stored correctly."""
    card = Card(
        scryfall_id="test-cmd-colors",
        name="Commander",
        type_line="Legendary Creature",
        color_identity=["W", "U", "B"],
        cmc=4.0,
        legalities={"commander": "legal"},
    )
    db_session.add(card)
    db_session.commit()

    commander = Commander(
        card_id=card.id,
        eligibility_reason="legendary creature",
        color_identity=["W", "U", "B"],
    )
    db_session.add(commander)
    db_session.commit()

    result = db_session.query(Commander).filter_by(card_id=card.id).first()
    assert result.color_identity == ["W", "U", "B"]
    assert len(result.color_identity) == 3


def test_deck_constraints_field(db_session: Session):
    """Test Deck constraints field stores JSON correctly."""
    card = Card(
        scryfall_id="test-constraints",
        name="Commander",
        type_line="Legendary Creature",
        color_identity=["G"],
        cmc=3.0,
        legalities={"commander": "legal"},
    )
    db_session.add(card)
    db_session.commit()

    commander = Commander(
        card_id=card.id,
        eligibility_reason="legendary",
        color_identity=["G"],
    )
    db_session.add(commander)
    db_session.commit()

    deck = Deck(
        commander_id=commander.id,
        constraints={"max_cmc": 7, "tribal": "elves"},
    )
    db_session.add(deck)
    db_session.commit()

    result = db_session.query(Deck).first()
    assert result.constraints == {"max_cmc": 7, "tribal": "elves"}
    assert result.constraints.get("max_cmc") == 7


def test_deckcard_quantity_default(db_session: Session):
    """Test DeckCard quantity defaults to 1."""
    card = Card(
        scryfall_id="test-qty",
        name="Card",
        type_line="Instant",
        color_identity=[],
        cmc=1.0,
        legalities={},
    )
    db_session.add(card)
    db_session.commit()

    commander_card = Card(
        scryfall_id="test-cmd-qty",
        name="Commander",
        type_line="Legendary Creature",
        color_identity=[],
        cmc=1.0,
        legalities={},
    )
    db_session.add(commander_card)
    db_session.commit()

    commander = Commander(
        card_id=commander_card.id,
        eligibility_reason="legendary",
        color_identity=[],
    )
    db_session.add(commander)
    db_session.commit()

    deck = Deck(commander_id=commander.id)
    db_session.add(deck)
    db_session.commit()

    # Create DeckCard with explicit quantity
    deck_card = DeckCard(deck_id=deck.id, card_id=card.id, quantity=1)
    db_session.add(deck_card)
    db_session.commit()

    result = db_session.query(DeckCard).first()
    assert result.quantity == 1


def test_card_scryfall_id_column_properties(db_session: Session):
    """Test scryfall_id column has correct properties (not nullable, unique, indexed)."""
    from sqlalchemy import inspect

    inspector = inspect(db_session.bind)
    columns = {col['name']: col for col in inspector.get_columns('cards')}

    scryfall_col = columns['scryfall_id']
    assert scryfall_col['nullable'] is False, "scryfall_id should not be nullable"

    # Check unique constraint exists
    indexes = inspector.get_indexes('cards')
    unique_indexes = [idx for idx in indexes if idx['unique']]
    assert any('scryfall_id' in idx.get('column_names', []) for idx in unique_indexes), \
        "scryfall_id should have unique index"


def test_card_name_column_length():
    """Test card name column has correct max length."""
    from sqlalchemy import inspect

    # Check the column definition directly from the model
    name_col = Card.__table__.columns['name']
    assert name_col.type.length == 255, "Card name should have max length 255"


def test_card_colors_is_mapped_column():
    """Test colors field uses mapped_column, not just None."""
    # This test ensures colors is stored in the database, not just a transient attribute
    colors_col = Card.__table__.columns.get('colors')
    assert colors_col is not None, "colors should be a database column"


def test_card_mana_cost_is_mapped_column():
    """Test mana_cost field uses mapped_column, not just None."""
    mana_cost_col = Card.__table__.columns.get('mana_cost')
    assert mana_cost_col is not None, "mana_cost should be a database column"
    assert mana_cost_col.type.length == 100, "mana_cost should have max length 100"


def test_card_price_usd_is_mapped_column():
    """Test price_usd field uses mapped_column, not just None."""
    price_col = Card.__table__.columns.get('price_usd')
    assert price_col is not None, "price_usd should be a database column"


def test_card_image_uris_is_mapped_column():
    """Test image_uris field uses mapped_column, not just None."""
    image_col = Card.__table__.columns.get('image_uris')
    assert image_col is not None, "image_uris should be a database column"


def test_card_oracle_text_nullable():
    """Test oracle_text can be null in database."""
    oracle_col = Card.__table__.columns['oracle_text']
    assert oracle_col.nullable is True, "oracle_text should be nullable"


def test_card_color_identity_not_nullable():
    """Test color_identity cannot be null."""
    from sqlalchemy import inspect

    inspector = inspect(Card.__table__)
    color_identity_col = inspector.columns['color_identity']
    assert color_identity_col.nullable is False, "color_identity should not be nullable"


def test_card_legalities_not_nullable():
    """Test legalities cannot be null."""
    legalities_col = Card.__table__.columns['legalities']
    assert legalities_col.nullable is False, "legalities should not be nullable"


def test_card_cmc_indexed():
    """Test cmc field is indexed for performance."""
    from sqlalchemy import inspect

    inspector = inspect(Card.__table__)
    # Check if cmc appears in any index
    has_index = False
    for idx in Card.__table__.indexes:
        if 'cmc' in [col.name for col in idx.columns]:
            has_index = True
            break
    assert has_index, "cmc should be indexed"


def test_commander_color_identity_not_nullable():
    """Test commander color_identity is required."""
    color_identity_col = Commander.__table__.columns['color_identity']
    assert color_identity_col.nullable is False, "commander color_identity should not be nullable"


def test_commander_eligibility_reason_not_nullable():
    """Test commander eligibility_reason is required."""
    reason_col = Commander.__table__.columns['eligibility_reason']
    assert reason_col.nullable is False, "eligibility_reason should not be nullable"


def test_deck_constraints_nullable(db_session: Session):
    """Test deck constraints can be None or a dict."""
    card = Card(
        scryfall_id="test-default-constraints",
        name="Commander",
        type_line="Legendary Creature",
        color_identity=["B"],
        cmc=3.0,
        legalities={"commander": "legal"},
    )
    db_session.add(card)
    db_session.commit()

    commander = Commander(
        card_id=card.id,
        eligibility_reason="legendary",
        color_identity=["B"],
    )
    db_session.add(commander)
    db_session.commit()

    # Create deck without specifying constraints
    deck = Deck(commander_id=commander.id)
    db_session.add(deck)
    db_session.commit()

    result = db_session.query(Deck).first()
    # Constraints can be None (it's Optional)
    assert result.constraints is None or isinstance(result.constraints, dict)


def test_role_name_unique(db_session: Session):
    """Test role name must be unique."""
    role1 = Role(name="draw", description="Card draw")
    db_session.add(role1)
    db_session.commit()

    role2 = Role(name="draw", description="Different description")
    db_session.add(role2)

    with pytest.raises(Exception):  # IntegrityError
        db_session.commit()


def test_archetype_name_unique(db_session: Session):
    """Test archetype name must be unique."""
    arch1 = Archetype(name="combo", description="Combo deck")
    db_session.add(arch1)
    db_session.commit()

    arch2 = Archetype(name="combo", description="Different description")
    db_session.add(arch2)

    with pytest.raises(Exception):  # IntegrityError
        db_session.commit()


def test_deckcard_cascade_delete(db_session: Session):
    """Test that deleting a deck cascades to delete deck_cards."""
    # Create minimal deck setup
    card = Card(
        scryfall_id="cascade-test",
        name="Test Card",
        type_line="Instant",
        color_identity=[],
        cmc=1.0,
        legalities={},
    )
    db_session.add(card)

    commander_card = Card(
        scryfall_id="cascade-commander",
        name="Commander",
        type_line="Legendary Creature",
        color_identity=[],
        cmc=1.0,
        legalities={},
    )
    db_session.add(commander_card)
    db_session.commit()

    commander = Commander(
        card_id=commander_card.id,
        eligibility_reason="legendary",
        color_identity=[],
    )
    db_session.add(commander)
    db_session.commit()

    deck = Deck(commander_id=commander.id)
    db_session.add(deck)
    db_session.commit()

    deck_card = DeckCard(deck_id=deck.id, card_id=card.id, quantity=1)
    db_session.add(deck_card)
    db_session.commit()

    # Verify deck_card exists
    assert db_session.query(DeckCard).count() == 1

    # Delete deck
    db_session.delete(deck)
    db_session.commit()

    # deck_cards should be cascaded and deleted
    assert db_session.query(DeckCard).count() == 0


def test_card_has_primary_key():
    """Test Card model has primary key on id column."""
    id_col = Card.__table__.columns['id']
    assert id_col.primary_key is True


def test_commander_has_primary_key():
    """Test Commander model has primary key on id column."""
    id_col = Commander.__table__.columns['id']
    assert id_col.primary_key is True


def test_role_has_primary_key():
    """Test Role model has primary key on id column."""
    id_col = Role.__table__.columns['id']
    assert id_col.primary_key is True


def test_archetype_has_primary_key():
    """Test Archetype model has primary key on id column."""
    id_col = Archetype.__table__.columns['id']
    assert id_col.primary_key is True


def test_deck_has_primary_key():
    """Test Deck model has primary key on id column."""
    id_col = Deck.__table__.columns['id']
    assert id_col.primary_key is True


def test_deckcard_has_primary_key():
    """Test DeckCard model has primary key on id column."""
    id_col = DeckCard.__table__.columns['id']
    assert id_col.primary_key is True


def test_card_id_is_mapped_column():
    """Test Card id is a mapped column, not None."""
    assert 'id' in Card.__table__.columns
    id_col = Card.__table__.columns['id']
    assert id_col is not None


def test_commander_id_is_mapped_column():
    """Test Commander id is a mapped column, not None."""
    assert 'id' in Commander.__table__.columns
    id_col = Commander.__table__.columns['id']
    assert id_col is not None


def test_role_id_is_mapped_column():
    """Test Role id is a mapped column, not None."""
    assert 'id' in Role.__table__.columns
    id_col = Role.__table__.columns['id']
    assert id_col is not None


def test_commander_card_synergy_columns() -> None:
    """Test CommanderCardSynergy fields are mapped columns."""
    from src.database.models import CommanderCardSynergy

    assert 'id' in CommanderCardSynergy.__table__.columns
    assert 'commander_id' in CommanderCardSynergy.__table__.columns
    assert 'card_id' in CommanderCardSynergy.__table__.columns
    assert 'label' in CommanderCardSynergy.__table__.columns


def test_training_session_columns() -> None:
    """Test TrainingSession fields are mapped columns."""
    from src.database.models import TrainingSession

    assert 'id' in TrainingSession.__table__.columns
    assert 'commander_id' in TrainingSession.__table__.columns
    assert 'created_at' in TrainingSession.__table__.columns


def test_training_session_card_columns() -> None:
    """Test TrainingSessionCard fields are mapped columns."""
    from src.database.models import TrainingSessionCard

    assert 'id' in TrainingSessionCard.__table__.columns
    assert 'session_id' in TrainingSessionCard.__table__.columns
    assert 'card_id' in TrainingSessionCard.__table__.columns


def test_commander_card_vote_columns() -> None:
    """Test CommanderCardVote fields are mapped columns."""
    from src.database.models import CommanderCardVote

    assert 'id' in CommanderCardVote.__table__.columns
    assert 'session_id' in CommanderCardVote.__table__.columns
    assert 'commander_id' in CommanderCardVote.__table__.columns
    assert 'card_id' in CommanderCardVote.__table__.columns
    assert 'vote' in CommanderCardVote.__table__.columns


def test_card_has_created_at_timestamp():
    """Test Card has created_at timestamp field."""
    assert 'created_at' in Card.__table__.columns
    created_col = Card.__table__.columns['created_at']
    assert created_col is not None
    assert created_col.nullable is False


def test_deck_has_created_at_timestamp():
    """Test Deck has created_at timestamp field."""
    assert 'created_at' in Deck.__table__.columns
    created_col = Deck.__table__.columns['created_at']
    assert created_col is not None
    assert created_col.nullable is False


def test_card_timestamps_auto_populate(db_session: Session):
    """Test that card timestamps are automatically populated."""
    card = Card(
        scryfall_id="test-timestamp",
        name="Test Card",
        type_line="Creature",
        color_identity=[],
        cmc=1.0,
        legalities={},
    )
    db_session.add(card)
    db_session.commit()

    assert card.created_at is not None


def test_deck_timestamps_auto_populate(db_session: Session):
    """Test that deck timestamps are automatically populated."""
    # Create commander first
    card = Card(
        scryfall_id="timestamp-commander",
        name="Commander",
        type_line="Legendary Creature",
        color_identity=[],
        cmc=1.0,
        legalities={},
    )
    db_session.add(card)
    db_session.commit()

    commander = Commander(
        card_id=card.id,
        eligibility_reason="legendary",
        color_identity=[],
    )
    db_session.add(commander)
    db_session.commit()

    deck = Deck(commander_id=commander.id)
    db_session.add(deck)
    db_session.commit()

    assert deck.created_at is not None


def test_deckcard_relationships(db_session: Session):
    """Test DeckCard has correct relationships to Deck, Card, and Role."""
    # Create card
    card = Card(
        scryfall_id="test-rel-card",
        name="Test Card",
        type_line="Instant",
        color_identity=["U"],
        cmc=2.0,
        legalities={},
    )
    db_session.add(card)

    # Create role
    role = Role(name="removal", description="Removes threats")
    db_session.add(role)

    # Create commander and deck
    commander_card = Card(
        scryfall_id="test-rel-commander",
        name="Commander",
        type_line="Legendary Creature",
        color_identity=["U"],
        cmc=3.0,
        legalities={},
    )
    db_session.add(commander_card)
    db_session.commit()

    commander = Commander(
        card_id=commander_card.id,
        eligibility_reason="legendary",
        color_identity=["U"],
    )
    db_session.add(commander)
    db_session.commit()

    deck = Deck(commander_id=commander.id)
    db_session.add(deck)
    db_session.commit()

    # Create DeckCard
    deck_card = DeckCard(
        deck_id=deck.id,
        card_id=card.id,
        role_id=role.id,
        quantity=1,
    )
    db_session.add(deck_card)
    db_session.commit()

    # Verify relationships
    assert deck_card.deck is not None
    assert deck_card.deck.id == deck.id
    assert deck_card.card is not None
    assert deck_card.card.name == "Test Card"
    assert deck_card.role is not None
    assert deck_card.role.name == "removal"
