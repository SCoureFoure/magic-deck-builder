from src.database.models import Card
from src.engine.archetypes import (
    compute_identity_from_deck,
    extract_archetype_tags,
    extract_identity,
    score_card_for_identity,
)


def make_card(name: str, type_line: str, oracle_text: str) -> Card:
    return Card(
        scryfall_id=f"{name}-id",
        name=name,
        type_line=type_line,
        oracle_text=oracle_text,
        colors=[],
        color_identity=[],
        mana_cost=None,
        cmc=0.0,
        legalities={"commander": "legal"},
        price_usd=None,
        image_uris=None,
    )


def test_extract_archetype_tags_voltron_and_equipment() -> None:
    card = make_card(
        "Sword of Tests",
        "Artifact — Equipment",
        "Equipped creature gets +2/+2 and has double strike.",
    )
    tags = extract_archetype_tags(card)
    assert tags["equipment"] > 0
    assert tags["voltron"] > 0


def test_extract_identity_normalizes_max_weight() -> None:
    commander = make_card(
        "Test Commander",
        "Legendary Creature — Human Warrior",
        "Double strike. Haste.",
    )
    seed = make_card(
        "Test Spell",
        "Instant",
        "Copy target instant or sorcery spell.",
    )
    identity = extract_identity(commander, [seed])
    assert identity
    assert max(identity.values()) == 1.0


def test_score_card_for_identity_prefers_matching_archetype() -> None:
    identity = {"voltron": 1.0}
    voltron_card = make_card(
        "Voltron Tool",
        "Artifact — Equipment",
        "Equipped creature gets +3/+3.",
    )
    off_theme = make_card("Off Theme", "Sorcery", "Draw two cards.")
    assert score_card_for_identity(voltron_card, identity) > score_card_for_identity(
        off_theme, identity
    )


def test_compute_identity_from_deck_blends_tags() -> None:
    commander = make_card(
        "Test Commander",
        "Legendary Creature — Human Warrior",
        "Double strike. Haste.",
    )
    deck_cards = [
        make_card(
            "Sword of Tests",
            "Artifact — Equipment",
            "Equipped creature gets +2/+2 and has double strike.",
        ),
        make_card(
            "Wheel of Tests",
            "Sorcery",
            "Each player discards their hand, then draws seven cards.",
        ),
    ]
    identity = compute_identity_from_deck(commander, deck_cards)
    assert identity
    assert "voltron" in identity
