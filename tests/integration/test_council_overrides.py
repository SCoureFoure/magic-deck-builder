from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base, Card, Commander
from src.engine.council.graph import select_cards_with_council


def _make_card(card_id: int, name: str) -> Card:
    return Card(
        id=card_id,
        scryfall_id=f"{name}-id",
        name=name,
        type_line="Instant",
        oracle_text="Test text",
        colors=None,
        color_identity=["U"],
        mana_cost="{U}",
        cmc=1.0,
        legalities={"commander": "legal"},
        price_usd=None,
        image_uris=None,
        card_faces=None,
    )


def test_council_overrides_respected() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        commander_card = _make_card(1, "Commander")
        session.add(commander_card)
        session.flush()
        commander = Commander(
            card_id=commander_card.id,
            eligibility_reason="legendary creature",
            color_identity=["U"],
        )
        session.add(commander)

        cards = [_make_card(idx, f"Card {idx}") for idx in range(2, 12)]
        session.add_all(cards)
        session.commit()

        result = select_cards_with_council(
            session=session,
            commander=commander,
            deck_cards=[commander_card],
            role="draw",
            count=3,
            exclude_ids=set(),
            overrides={
                "routing": {
                    "strategy": "parallel",
                    "agent_ids": ["heuristic-core"],
                },
                "agents": [
                    {"id": "heuristic-core", "type": "heuristic", "weight": 1.0}
                ],
            },
        )

        assert len(result) == 3
