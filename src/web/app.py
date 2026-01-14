"""FastAPI app for commander search UI."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.database.engine import get_db
from src.engine.commander import find_commanders, is_commander_eligible, populate_commanders


class CommanderResult(BaseModel):
    """API response for a commander search result."""

    name: str
    type_line: str
    color_identity: list[str]
    mana_cost: Optional[str]
    cmc: float
    eligibility: Optional[str]
    commander_legal: str


class CommanderSearchResponse(BaseModel):
    """API response for commander search."""

    query: str
    count: int
    results: list[CommanderResult]


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
                )
            )

    return CommanderSearchResponse(query=query, count=len(mapped_results), results=mapped_results)
