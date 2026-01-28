"""FastAPI app for commander search UI."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.web.routes import commanders, council, decks, health, training

app = FastAPI(title="Magic Deck Builder API", version="0.1.0")
logging.basicConfig(level=logging.INFO)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=settings.cors_allows_credentials(),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(commanders.router)
app.include_router(decks.router)
app.include_router(training.router)
app.include_router(council.router)
