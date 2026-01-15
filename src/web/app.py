"""FastAPI app for commander search UI."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.database.engine import get_db
from src.database.seed_roles import seed_roles
from src.engine.commander import create_commander_entry, find_commanders, is_commander_eligible, populate_commanders
from src.engine.deck_builder import generate_deck
from src.engine.validator import validate_deck


class CommanderResult(BaseModel):
    """API response for a commander search result."""

    name: str
    type_line: str
    color_identity: list[str]
    mana_cost: Optional[str]
    cmc: float
    eligibility: Optional[str]
    commander_legal: str
    image_url: Optional[str]


class CommanderSearchResponse(BaseModel):
    """API response for commander search."""

    query: str
    count: int
    results: list[CommanderResult]


class DeckGenerationRequest(BaseModel):
    """Request body for deck generation."""

    commander_name: str


class DeckCardResult(BaseModel):
    """A card in the generated deck."""

    name: str
    quantity: int
    role: str
    type_line: str
    mana_cost: Optional[str]
    cmc: float
    image_url: Optional[str]


class DeckGenerationResponse(BaseModel):
    """API response for deck generation."""

    commander_name: str
    total_cards: int
    is_valid: bool
    validation_errors: list[str]
    cards_by_role: dict[str, list[DeckCardResult]]


app = FastAPI(title="Magic Deck Builder API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> dict[str, Any]:
    """Basic health check endpoint."""
    return {"status": "ok"}


@app.get("/api/commanders", response_model=CommanderSearchResponse)
def search_commanders(
    query: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(10, ge=1, le=50),
    populate: bool = False,
) -> CommanderSearchResponse:
    """Search for commanders by name."""
    with get_db() as db:
        if populate:
            populate_commanders(db)
        results = find_commanders(db, name_query=query, limit=limit)

        if not results:
            raise HTTPException(status_code=404, detail="No commanders found")

        mapped_results: list[CommanderResult] = []
        for card in results:
            is_eligible, reason = is_commander_eligible(card)
            mapped_results.append(
                CommanderResult(
                    name=card.name,
                    type_line=card.type_line,
                    color_identity=card.color_identity or [],
                    mana_cost=card.mana_cost,
                    cmc=card.cmc,
                    eligibility=reason if is_eligible else None,
                    commander_legal=card.legalities.get("commander", "unknown"),
                    image_url=(card.image_uris or {}).get("normal")
                    if card.image_uris
                    else None,
                )
            )

    return CommanderSearchResponse(query=query, count=len(mapped_results), results=mapped_results)


@app.post("/api/decks/generate", response_model=DeckGenerationResponse)
def generate_deck_endpoint(request: DeckGenerationRequest) -> DeckGenerationResponse:
    """Generate a 100-card Commander deck."""
    with get_db() as db:
        # Find commander
        commanders = find_commanders(db, name_query=request.commander_name, limit=1)

        if not commanders:
            raise HTTPException(
                status_code=404,
                detail=f"Commander '{request.commander_name}' not found"
            )

        commander_card = commanders[0]

        # Get or create commander entry
        commander = create_commander_entry(db, commander_card)

        if not commander:
            raise HTTPException(
                status_code=500,
                detail="Could not create commander entry"
            )

        # Seed roles if needed
        seed_roles(db)

        # Generate deck
        deck = generate_deck(db, commander)

        # Validate deck
        is_valid, errors = validate_deck(deck)

        # Group cards by role
        from collections import defaultdict
        cards_by_role: dict[str, list[DeckCardResult]] = defaultdict(list)

        for deck_card in deck.deck_cards:
            role_name = deck_card.role.name if deck_card.role else "unknown"

            card_result = DeckCardResult(
                name=deck_card.card.name,
                quantity=deck_card.quantity,
                role=role_name,
                type_line=deck_card.card.type_line,
                mana_cost=deck_card.card.mana_cost,
                cmc=deck_card.card.cmc,
                image_url=(deck_card.card.image_uris or {}).get("normal")
                if deck_card.card.image_uris
                else None,
            )
            cards_by_role[role_name].append(card_result)

        # Calculate total cards
        total_cards = sum(dc.quantity for dc in deck.deck_cards)

        return DeckGenerationResponse(
            commander_name=commander_card.name,
            total_cards=total_cards,
            is_valid=is_valid,
            validation_errors=errors,
            cards_by_role=dict(cards_by_role)
        )
