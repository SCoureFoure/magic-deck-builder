"""Integration tests for web API routes."""
from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")

from src.database.models import Base, Card, Commander, CommanderCardVote, TrainingSession
from src.engine.commander import create_commander_entry
from src.engine.council.config import AgentConfig, CouncilConfig
from src.web import app as web_app
from src.web.routes import commanders, council, decks, training


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def get_db_override(db_session):
    @contextmanager
    def _get_db() -> Generator:
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    return _get_db


@pytest.fixture
def client(monkeypatch, get_db_override):
    monkeypatch.setattr(commanders, "get_db", get_db_override)
    monkeypatch.setattr(decks, "get_db", get_db_override)
    monkeypatch.setattr(training, "get_db", get_db_override)
    monkeypatch.setattr(council, "get_db", get_db_override)

    return TestClient(web_app.app)


def _create_card(
    db_session,
    *,
    name: str,
    type_line: str,
    color_identity: list[str],
    cmc: float = 3.0,
):
    card = Card(
        scryfall_id=f"{name.lower().replace(' ', '-')}-id",
        name=name,
        type_line=type_line,
        oracle_text="Test oracle text",
        color_identity=color_identity,
        colors=color_identity,
        cmc=cmc,
        legalities={"commander": "legal"},
        image_uris={"normal": "http://example.com/image.png"},
    )
    db_session.add(card)
    db_session.commit()
    return card


def _create_commander(db_session, *, name: str, color_identity: list[str]) -> Commander:
    card = _create_card(
        db_session,
        name=name,
        type_line="Legendary Creature — Test",
        color_identity=color_identity,
    )
    commander = create_commander_entry(db_session, card)
    db_session.commit()
    return commander


def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_commanders_search(client, db_session, monkeypatch):
    monkeypatch.setattr(commanders.settings, "enable_scryfall_fallback", False, raising=False)
    _create_card(
        db_session,
        name="Test Commander",
        type_line="Legendary Creature — Wizard",
        color_identity=["U"],
    )

    response = client.get("/api/commanders", params={"query": "Test", "limit": 5})
    payload = response.json()

    assert response.status_code == 200
    assert payload["count"] == 1
    assert payload["results"][0]["name"] == "Test Commander"


def test_commander_synergy_endpoints(client, db_session):
    commander = _create_commander(db_session, name="Synergy Commander", color_identity=["G"])
    candidate = _create_card(
        db_session,
        name="Synergy Card",
        type_line="Creature — Elf",
        color_identity=["G"],
    )

    session = TrainingSession(commander_id=commander.id)
    db_session.add(session)
    db_session.commit()

    db_session.add(
        CommanderCardVote(
            session_id=session.id,
            commander_id=commander.id,
            card_id=candidate.id,
            vote=1,
        )
    )
    db_session.commit()

    response = client.get(
        f"/api/commanders/{commander.card.name}/synergy",
        params={"query": "Synergy"},
    )
    assert response.status_code == 200
    assert response.json()[0]["card_name"] == "Synergy Card"

    response = client.get(
        f"/api/commanders/{commander.card.name}/synergy/top",
        params={"limit": 5, "min_ratio": 0.5},
    )
    assert response.status_code == 200
    assert response.json()[0]["card_name"] == "Synergy Card"


def test_deck_generate_endpoint(client, db_session, monkeypatch):
    commander = _create_commander(db_session, name="Deck Commander", color_identity=["U"])
    deck_card = _create_card(
        db_session,
        name="Deck Card",
        type_line="Artifact",
        color_identity=[],
    )

    @dataclass
    class DummyRole:
        name: str

    @dataclass
    class DummyDeckCard:
        card: Card
        quantity: int
        role: DummyRole

    @dataclass
    class DummyDeck:
        deck_cards: list[DummyDeckCard]

    @dataclass
    class DummySource:
        source_type: str
        details: dict[str, object]
        card_ids: list[int]
        card_names: list[str]

    @dataclass
    class DummyBuildOutput:
        deck: DummyDeck
        sources_by_role: dict[str, list[DummySource]]

    monkeypatch.setattr(decks, "seed_roles", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(decks, "validate_deck", lambda *_args, **_kwargs: (True, []))
    monkeypatch.setattr(decks, "compute_coherence_metrics", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(decks, "extract_identity", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(decks, "compute_identity_from_deck", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(decks, "score_card_for_identity", lambda *_args, **_kwargs: 0.5)

    build_output = DummyBuildOutput(
        deck=DummyDeck(
            deck_cards=[
                DummyDeckCard(card=deck_card, quantity=1, role=DummyRole(name="ramp"))
            ]
        ),
        sources_by_role={
            "ramp": [
                DummySource(
                    source_type="seed",
                    details={"reason": "test"},
                    card_ids=[deck_card.id],
                    card_names=[deck_card.name],
                )
            ]
        },
    )

    monkeypatch.setattr(decks, "generate_deck_with_attribution", lambda *_args, **_kwargs: build_output)

    response = client.post(
        "/api/decks/generate",
        json={
            "commander_name": commander.card.name,
            "use_llm_agent": False,
            "use_council": False,
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["commander_name"] == commander.card.name
    assert payload["total_cards"] == 1
    assert payload["cards_by_role"]["ramp"][0]["name"] == "Deck Card"


def test_training_endpoints(client, db_session, monkeypatch):
    monkeypatch.setattr(training.random, "shuffle", lambda _cards: None)

    _create_commander(db_session, name="Training Commander", color_identity=["R"])
    candidate = _create_card(
        db_session,
        name="Training Candidate",
        type_line="Creature — Warrior",
        color_identity=["R"],
    )

    response = client.post("/api/training/session/start")
    payload = response.json()
    assert response.status_code == 200

    session_id = payload["session_id"]

    response = client.get(f"/api/training/session/{session_id}/next")
    assert response.status_code == 200
    assert response.json()["card"]["name"] == candidate.name

    response = client.post(
        "/api/training/session/vote",
        json={"session_id": session_id, "card_id": candidate.id, "vote": 1},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    response = client.get("/api/training/stats")
    assert response.status_code == 200
    assert response.json()["total_votes"] == 1


def test_council_endpoints(client, db_session, monkeypatch):
    commander = _create_commander(db_session, name="Council Commander", color_identity=["W"])
    card = _create_card(
        db_session,
        name="Council Card",
        type_line="Creature — Knight",
        color_identity=["W"],
    )

    session = TrainingSession(commander_id=commander.id)
    db_session.add(session)
    db_session.commit()

    config = CouncilConfig(agents=[AgentConfig(agent_id="rule-1", agent_type="heuristic")])
    monkeypatch.setattr(council, "load_council_config", lambda *_args, **_kwargs: config)
    monkeypatch.setattr(
        council,
        "council_training_opinions",
        lambda *_args, **_kwargs: [
            {
                "agent_id": "rule-1",
                "display_name": "Rule One",
                "agent_type": "heuristic",
                "weight": 1.0,
                "score": 0.8,
                "metrics": "ok",
                "reason": "test",
            }
        ],
    )
    monkeypatch.setattr(council, "council_training_synthesis", lambda *_args, **_kwargs: "approve")

    response = client.get("/api/council/agents")
    assert response.status_code == 200
    assert response.json()[0]["id"] == "rule-1"

    response = client.post(
        "/api/council/agent/import",
        json={"yaml": "id: rule-2\ntype: heuristic\nweight: 1.0\n"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == "rule-2"

    response = client.post(
        "/api/council/agent/export",
        json={
            "id": "rule-3",
            "type": "heuristic",
            "weight": 1.0,
            "temperature": 0.3,
            "preferences": {
                "theme_weight": 0.5,
                "efficiency_weight": 0.25,
                "budget_weight": 0.25,
                "price_cap_usd": None,
            },
        },
    )
    assert response.status_code == 200
    assert "rule-3" in response.json()["yaml"]

    response = client.post(
        "/api/training/council/consult",
        json={
            "session_id": session.id,
            "card_id": card.id,
            "api_key": "test-key",
            "agents": [
                {
                    "id": "rule-1",
                    "type": "heuristic",
                    "weight": 1.0,
                    "temperature": 0.3,
                    "preferences": {
                        "theme_weight": 0.5,
                        "efficiency_weight": 0.25,
                        "budget_weight": 0.25,
                        "price_cap_usd": None,
                    },
                }
            ],
            "synthesizer": {
                "id": "rule-1",
                "type": "heuristic",
                "weight": 1.0,
                "temperature": 0.3,
                "preferences": {
                    "theme_weight": 0.5,
                    "efficiency_weight": 0.25,
                    "budget_weight": 0.25,
                    "price_cap_usd": None,
                },
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["verdict"] == "approve"

    response = client.post(
        "/api/training/council/analyze",
        json={
            "session_id": session.id,
            "card_id": card.id,
            "api_key": "test-key",
        },
    )
    assert response.status_code == 200
    assert response.json()["opinions"][0]["agent_id"] == "rule-1"
