"""Tests for bulk ingestion utilities."""
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base, Card
from src.ingestion.bulk_ingest import (
    ingest_bulk_file,
    map_card_data,
    select_bulk_download_url,
    upsert_cards,
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


def test_select_bulk_download_url():
    """Select the correct download URI for a bulk type."""
    bulk_info = {
        "data": [
            {"type": "oracle_cards", "download_uri": "https://example.com/oracle.json"},
            {"type": "default_cards", "download_uri": "https://example.com/default.json"},
        ]
    }
    url = select_bulk_download_url(bulk_info, "oracle_cards")
    assert url == "https://example.com/oracle.json"


def test_select_bulk_download_url_not_found():
    """Raise ValueError when bulk type is not found."""
    bulk_info = {"data": []}
    with pytest.raises(ValueError, match="Bulk data type not found: missing_type"):
        select_bulk_download_url(bulk_info, "missing_type")


def test_map_card_data_uses_face_images():
    """Map card data and pick image_uris from card_faces if needed."""
    card_data = {
        "id": "abc",
        "name": "Test Card",
        "type_line": "Creature",
        "oracle_text": "Test",
        "colors": ["G"],
        "color_identity": ["G"],
        "mana_cost": "{G}",
        "cmc": 1,
        "legalities": {"commander": "legal"},
        "prices": {"usd": "1.23"},
        "card_faces": [{"image_uris": {"normal": "https://example.com/face.png"}}],
    }
    mapped = map_card_data(card_data)
    assert mapped["image_uris"] == {"normal": "https://example.com/face.png"}
    assert mapped["card_faces"] == [{"image_uris": {"normal": "https://example.com/face.png"}}]


def test_upsert_cards_inserts_and_updates(db_session: Session):
    """Insert new cards and update existing ones by scryfall_id."""
    card_data = {
        "object": "card",
        "id": "card-1",
        "name": "Test Card",
        "type_line": "Artifact",
        "oracle_text": "Original",
        "colors": [],
        "color_identity": [],
        "mana_cost": "{1}",
        "cmc": 1,
        "legalities": {"commander": "legal"},
        "prices": {"usd": "1.00"},
    }
    processed = upsert_cards(db_session, [card_data])
    assert processed == 1

    stored = db_session.query(Card).filter_by(scryfall_id="card-1").one()
    assert stored.oracle_text == "Original"

    card_data_updated = dict(card_data)
    card_data_updated["oracle_text"] = "Updated"
    processed = upsert_cards(db_session, [card_data_updated])
    assert processed == 1

    stored = db_session.query(Card).filter_by(scryfall_id="card-1").one()
    assert stored.oracle_text == "Updated"


def test_ingest_bulk_file(db_session: Session, tmp_path: Path):
    """Ingest a local bulk JSON file."""
    bulk_path = tmp_path / "bulk.json"
    bulk_path.write_text(
        '[{"object": "card", "id": "card-2", "name": "Bulk Card", '
        '"type_line": "Artifact", "oracle_text": "Bulk", '
        '"colors": [], "color_identity": [], "mana_cost": "{1}", '
        '"cmc": 1, "legalities": {"commander": "legal"}}]'
    )

    processed = ingest_bulk_file(db_session, bulk_path)
    assert processed == 1
    stored = db_session.query(Card).filter_by(scryfall_id="card-2").one()
    assert stored.name == "Bulk Card"


def test_upsert_skips_non_card_objects(db_session: Session):
    """Skip objects that are not cards."""
    data = [
        {"object": "list", "id": "skip-me"},
        {"object": "set", "id": "skip-me-too"},
        {
            "object": "card",
            "id": "keep-me",
            "name": "Valid Card",
            "type_line": "Artifact",
            "color_identity": [],
            "cmc": 1,
            "legalities": {"commander": "legal"},
        },
    ]

    processed = upsert_cards(db_session, data)
    assert processed == 1  # Only the card object should be processed

    # Verify only the valid card was inserted
    cards = db_session.query(Card).all()
    assert len(cards) == 1
    assert cards[0].name == "Valid Card"


def test_upsert_skips_cards_without_id(db_session: Session):
    """Skip cards that don't have an id field."""
    data = [
        {
            "object": "card",
            # Missing "id" field
            "name": "No ID Card",
            "type_line": "Artifact",
            "color_identity": [],
            "cmc": 1,
            "legalities": {"commander": "legal"},
        }
    ]

    processed = upsert_cards(db_session, data)
    assert processed == 0  # Should skip

    # Verify nothing was inserted
    cards = db_session.query(Card).all()
    assert len(cards) == 0


def test_ingest_bulk_file_invalid_json(db_session: Session, tmp_path: Path):
    """Raise error when bulk file contains invalid JSON."""
    bulk_path = tmp_path / "invalid.json"
    bulk_path.write_text("not valid json")

    with pytest.raises(json.JSONDecodeError):
        ingest_bulk_file(db_session, bulk_path)


def test_ingest_bulk_file_not_a_list(db_session: Session, tmp_path: Path):
    """Raise error when bulk file doesn't contain a list."""
    bulk_path = tmp_path / "not_list.json"
    bulk_path.write_text('{"object": "card", "id": "test"}')

    with pytest.raises(ValueError, match="Bulk file did not contain a list"):
        ingest_bulk_file(db_session, bulk_path)
