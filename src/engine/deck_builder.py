"""Deck generation engine for Commander decks."""
from __future__ import annotations

from dataclasses import dataclass, field
from sqlalchemy.orm import Session

from src.database.models import Card, Commander, Deck, DeckCard, Role
from src.engine.archetypes import extract_identity
from src.engine.context import SourceAttribution
from src.engine.council import select_cards_with_council
from src.engine.council.graph import select_cards_with_council_with_attribution
from src.engine.llm_agent import suggest_cards_for_role, suggest_cards_with_attribution
from src.engine.lands import calculate_land_distribution, needs_command_tower
from src.engine.selector import select_basic_lands, select_cards_for_role, select_command_tower


@dataclass(frozen=True)
class DeckBuildOutput:
    deck: Deck
    sources_by_role: dict[str, list[SourceAttribution]] = field(default_factory=dict)


def _generate_deck_internal(
    session: Session,
    commander: Commander,
    constraints: dict | None = None,
    collect_attribution: bool = False,
) -> DeckBuildOutput:
    """Generate a legal 100-card Commander deck.

    Uses standard template: 37 lands / 10 ramp / 10 draw / 10 removal /
    25 synergy / 5 wincons / 3 flex

    Args:
        session: Database session
        commander: Commander for the deck
        constraints: Optional deck building constraints (future use)

    Returns:
        Generated Deck object with all cards

    Raises:
        ValueError: If deck cannot be generated
    """
    # Create deck record
    deck = Deck(commander_id=commander.id, constraints=constraints or {})
    session.add(deck)
    session.flush()  # Get deck.id

    # Get role IDs for tagging
    roles = {role.name: role.id for role in session.query(Role).all()}

    # Track selected card IDs to avoid duplicates
    selected_ids: set[int] = set()
    sources_by_role: dict[str, list[SourceAttribution]] = {}

    # Step 1: Add commander (counts as 1 of the 100 cards)
    commander_card = commander.card
    deck_card = DeckCard(
        deck_id=deck.id,
        card_id=commander_card.id,
        role_id=roles.get("synergy"),  # Commander drives synergy
        quantity=1,
        locked=True,
    )
    session.add(deck_card)
    selected_ids.add(commander_card.id)

    # Step 2: Calculate and add lands
    land_dist = calculate_land_distribution(commander.color_identity or [])

    # Add Command Tower if multicolor
    if needs_command_tower(commander.color_identity or []):
        command_tower = select_command_tower(session)
        if command_tower and command_tower.id not in selected_ids:
            deck_card = DeckCard(
                deck_id=deck.id,
                card_id=command_tower.id,
                role_id=roles.get("lands"),
                quantity=1,
                locked=False,
            )
            session.add(deck_card)
            selected_ids.add(command_tower.id)

    # Add basic lands
    basics = select_basic_lands(session, land_dist)
    # Group by card ID to handle quantities
    basic_counts: dict[int, int] = {}
    for basic in basics:
        basic_counts[basic.id] = basic_counts.get(basic.id, 0) + 1

    for card_id, quantity in basic_counts.items():
        deck_card = DeckCard(
            deck_id=deck.id,
            card_id=card_id,
            role_id=roles.get("lands"),
            quantity=quantity,
            locked=False,
        )
        session.add(deck_card)
        selected_ids.add(card_id)

    # Step 3: Select non-land cards by role
    seed_names = (constraints or {}).get("seeds", [])
    seed_cards = (
        session.query(Card).filter(Card.name.in_(seed_names)).all()
        if seed_names
        else []
    )
    identity = extract_identity(commander_card, seed_cards)

    role_targets = [
        ("ramp", 10),
        ("draw", 10),
        ("removal", 10),
        ("wincons", 5),
        ("flex", 3),
    ]

    # Track cards by role as we select them
    cards_by_role: dict[str, list[Card]] = {}
    shortfall = 0

    use_llm_agent = bool((constraints or {}).get("use_llm_agent"))
    use_council = bool((constraints or {}).get("use_council"))
    council_overrides = (constraints or {}).get("council_overrides")
    council_config_path = (constraints or {}).get("council_config_path")
    trace_id = (constraints or {}).get("trace_id")
    current_cards: list[Card] = [commander_card]

    for role_name, target_count in role_targets:
        cards: list[Card] = []
        attributions: list[SourceAttribution] = []
        if use_council:
            if collect_attribution:
                cards, attributions = select_cards_with_council_with_attribution(
                    session=session,
                    commander=commander,
                    deck_cards=current_cards,
                    role=role_name,
                    count=target_count,
                    exclude_ids=selected_ids,
                    config_path=council_config_path,
                    overrides=council_overrides,
                    trace_id=trace_id,
                    deck_id=deck.id,
                )
            else:
                cards = select_cards_with_council(
                    session=session,
                    commander=commander,
                    deck_cards=current_cards,
                    role=role_name,
                    count=target_count,
                    exclude_ids=selected_ids,
                    config_path=council_config_path,
                    overrides=council_overrides,
                    trace_id=trace_id,
                    deck_id=deck.id,
                )
        elif use_llm_agent:
            if collect_attribution:
                cards, attributions = suggest_cards_with_attribution(
                    session=session,
                    deck_id=deck.id,
                    commander=commander,
                    deck_cards=current_cards,
                    role=role_name,
                    count=target_count,
                    exclude_ids=selected_ids,
                    trace_id=trace_id,
                )
            else:
                cards = suggest_cards_for_role(
                    session=session,
                    deck_id=deck.id,
                    commander=commander,
                    deck_cards=current_cards,
                    role=role_name,
                    count=target_count,
                    exclude_ids=selected_ids,
                    trace_id=trace_id,
                )

        if len(cards) < target_count:
            remaining = target_count - len(cards)
            fallback = select_cards_for_role(
                session,
                role_name,
                commander.color_identity or [],
                remaining,
                identity,
                selected_ids,
            )
            cards.extend(fallback)
            if collect_attribution:
                attributions.append(
                    SourceAttribution(
                        source_type="fallback_selection",
                        details={"role": role_name, "count": len(fallback)},
                        card_ids=[card.id for card in fallback],
                        card_names=[card.name for card in fallback],
                    )
                )
        if collect_attribution and attributions:
            sources_by_role.setdefault(role_name, []).extend(attributions)
        cards_by_role[role_name] = cards
        for card in cards:
            selected_ids.add(card.id)
            current_cards.append(card)

        if len(cards) < target_count:
            shortfall += target_count - len(cards)

    # Step 4: Fill synergy pool + handle shortfalls
    # Commander counts as 1 synergy card, so we need 24 more + shortfall
    synergy_target = 24 + shortfall
    synergy_cards: list[Card] = []
    synergy_attributions: list[SourceAttribution] = []
    if use_council:
        if collect_attribution:
            synergy_cards, synergy_attributions = select_cards_with_council_with_attribution(
                session=session,
                commander=commander,
                deck_cards=current_cards,
                role="synergy",
                count=synergy_target,
                exclude_ids=selected_ids,
                config_path=council_config_path,
                overrides=council_overrides,
                trace_id=trace_id,
                deck_id=deck.id,
            )
        else:
            synergy_cards = select_cards_with_council(
                session=session,
                commander=commander,
                deck_cards=current_cards,
                role="synergy",
                count=synergy_target,
                exclude_ids=selected_ids,
                config_path=council_config_path,
                overrides=council_overrides,
                trace_id=trace_id,
                deck_id=deck.id,
            )
    elif use_llm_agent:
        if collect_attribution:
            synergy_cards, synergy_attributions = suggest_cards_with_attribution(
                session=session,
                deck_id=deck.id,
                commander=commander,
                deck_cards=current_cards,
                role="synergy",
                count=synergy_target,
                exclude_ids=selected_ids,
                trace_id=trace_id,
            )
        else:
            synergy_cards = suggest_cards_for_role(
                session=session,
                deck_id=deck.id,
                commander=commander,
                deck_cards=current_cards,
                role="synergy",
                count=synergy_target,
                exclude_ids=selected_ids,
                trace_id=trace_id,
            )

    if len(synergy_cards) < synergy_target:
        remaining = synergy_target - len(synergy_cards)
        fallback = select_cards_for_role(
            session,
            "synergy",
            commander.color_identity or [],
            remaining,
            identity,
            selected_ids,
        )
        synergy_cards.extend(fallback)
        if collect_attribution:
            synergy_attributions.append(
                SourceAttribution(
                    source_type="fallback_selection",
                    details={"role": "synergy", "count": len(fallback)},
                    card_ids=[card.id for card in fallback],
                    card_names=[card.name for card in fallback],
                )
            )
    if collect_attribution and synergy_attributions:
        sources_by_role.setdefault("synergy", []).extend(synergy_attributions)
    cards_by_role["synergy"] = synergy_cards

    # Step 5: Add non-land cards to deck with correct role assignments
    for role_name, cards in cards_by_role.items():
        role_id = roles.get(role_name)
        for card in cards:
            deck_card = DeckCard(
                deck_id=deck.id,
                card_id=card.id,
                role_id=role_id,
                quantity=1,
                locked=False,
            )
            session.add(deck_card)

    session.commit()
    session.refresh(deck)
    return DeckBuildOutput(deck=deck, sources_by_role=sources_by_role)


def generate_deck(
    session: Session, commander: Commander, constraints: dict | None = None
) -> Deck:
    """Generate a legal 100-card Commander deck."""
    result = _generate_deck_internal(
        session=session,
        commander=commander,
        constraints=constraints,
        collect_attribution=False,
    )
    return result.deck


def generate_deck_with_attribution(
    session: Session, commander: Commander, constraints: dict | None = None
) -> DeckBuildOutput:
    """Generate a deck and return source attribution details."""
    return _generate_deck_internal(
        session=session,
        commander=commander,
        constraints=constraints,
        collect_attribution=True,
    )
