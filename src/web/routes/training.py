"""Training session routes."""
from __future__ import annotations

import random
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import case, func

from src.database.engine import get_db
from src.database.models import (
    Card,
    Commander,
    CommanderCardSynergy,
    CommanderCardVote,
    TrainingSession,
    TrainingSessionCard,
)
from src.web.schemas import (
    TrainingCardResponse,
    TrainingCardStat,
    TrainingCommanderSummary,
    TrainingSessionResponse,
    TrainingStatsResponse,
    TrainingVoteRequest,
)
from src.web.serializers import training_card_from_card

router = APIRouter()


@router.post("/api/training/session/start", response_model=TrainingSessionResponse)
def training_session_start() -> TrainingSessionResponse:
    """Start a new training session with a random commander."""
    with get_db() as db:
        commander = db.query(Commander).order_by(func.random()).first()
        if not commander:
            raise HTTPException(status_code=404, detail="No commanders available")

        commander_card = commander.card

        session = TrainingSession(commander_id=commander.id)
        db.add(session)
        db.flush()

        return TrainingSessionResponse(
            session_id=session.id,
            commander=training_card_from_card(commander_card),
        )


@router.get("/api/training/session/{session_id}/next", response_model=TrainingCardResponse)
def training_session_next(session_id: int) -> TrainingCardResponse:
    """Return the next unseen card for a training session."""
    with get_db() as db:
        session = db.query(TrainingSession).filter(TrainingSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        commander = session.commander
        commander_card = commander.card
        commander_colors = set(commander.color_identity or [])
        seen_card_ids = {
            row.card_id
            for row in db.query(TrainingSessionCard.card_id)
            .filter(TrainingSessionCard.session_id == session.id)
            .all()
        }

        candidates = (
            db.query(Card)
            .filter(Card.legalities["commander"].as_string() == "legal")
            .limit(5000)
            .all()
        )
        random.shuffle(candidates)
        chosen: Card | None = None
        for card in candidates:
            if card.id == commander_card.id:
                continue
            if card.id in seen_card_ids:
                continue
            card_colors = set(card.color_identity or [])
            if not card_colors.issubset(commander_colors):
                continue
            chosen = card
            break

        if not chosen:
            raise HTTPException(status_code=404, detail="No candidate cards found")

        db.add(TrainingSessionCard(session_id=session.id, card_id=chosen.id))
        db.flush()

        return TrainingCardResponse(
            session_id=session.id,
            card=training_card_from_card(chosen),
        )


@router.post("/api/training/session/vote")
def training_session_vote(request: TrainingVoteRequest) -> dict[str, Any]:
    """Store a synergy vote (0/1) for a session card."""
    if request.vote not in (0, 1):
        raise HTTPException(status_code=400, detail="Vote must be 0 or 1")

    with get_db() as db:
        session = db.query(TrainingSession).filter(TrainingSession.id == request.session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        session_card = (
            db.query(TrainingSessionCard)
            .filter(
                TrainingSessionCard.session_id == session.id,
                TrainingSessionCard.card_id == request.card_id,
            )
            .first()
        )
        if not session_card:
            raise HTTPException(status_code=400, detail="Card not in session")

        existing_vote = (
            db.query(CommanderCardVote)
            .filter(
                CommanderCardVote.session_id == session.id,
                CommanderCardVote.card_id == request.card_id,
            )
            .first()
        )
        if existing_vote:
            raise HTTPException(status_code=400, detail="Vote already recorded")

        db.add(
            CommanderCardVote(
                session_id=session.id,
                commander_id=session.commander_id,
                card_id=request.card_id,
                vote=request.vote,
            )
        )

        synergy = (
            db.query(CommanderCardSynergy)
            .filter(
                CommanderCardSynergy.commander_id == session.commander_id,
                CommanderCardSynergy.card_id == request.card_id,
            )
            .first()
        )
        if synergy:
            synergy.label = request.vote
        else:
            db.add(
                CommanderCardSynergy(
                    commander_id=session.commander_id,
                    card_id=request.card_id,
                    label=request.vote,
                )
            )

        db.commit()
        return {"status": "ok"}


@router.get("/api/training/stats", response_model=TrainingStatsResponse)
def training_stats() -> TrainingStatsResponse:
    """Return aggregate training stats."""
    with get_db() as db:
        total_votes = db.query(func.count(CommanderCardVote.id)).scalar() or 0

        yes_case = case((CommanderCardVote.vote == 1, 1), else_=0)
        no_case = case((CommanderCardVote.vote == 0, 1), else_=0)

        commander_rows = (
            db.query(
                Commander.id,
                Card.name.label("commander_name"),
                func.sum(yes_case).label("yes"),
                func.sum(no_case).label("no"),
            )
            .join(Commander, Commander.id == CommanderCardVote.commander_id)
            .join(Card, Card.id == Commander.card_id)
            .group_by(Commander.id, Card.name)
            .all()
        )

        card_rows = (
            db.query(
                CommanderCardVote.commander_id,
                Card.name.label("card_name"),
                func.sum(yes_case).label("yes"),
                func.sum(no_case).label("no"),
            )
            .join(Card, Card.id == CommanderCardVote.card_id)
            .group_by(CommanderCardVote.commander_id, Card.name)
            .all()
        )

        commander_stats: dict[int, TrainingCommanderSummary] = {}
        for commander_id, commander_name, yes, no in commander_rows:
            total = (yes or 0) + (no or 0)
            ratio = (yes or 0) / total if total else 0.0
            commander_stats[commander_id] = TrainingCommanderSummary(
                commander_name=commander_name,
                yes=yes or 0,
                no=no or 0,
                ratio=ratio,
                cards=[],
            )

        for commander_id, card_name, yes, no in card_rows:
            total = (yes or 0) + (no or 0)
            ratio = (yes or 0) / total if total else 0.0
            if commander_id not in commander_stats:
                commander_stats[commander_id] = TrainingCommanderSummary(
                    commander_name="Unknown",
                    yes=0,
                    no=0,
                    ratio=0.0,
                    cards=[],
                )
            commander_stats[commander_id].cards.append(
                TrainingCardStat(card_name=card_name, yes=yes or 0, no=no or 0, ratio=ratio)
            )

        commanders = sorted(
            commander_stats.values(),
            key=lambda item: (-(item.yes + item.no), item.commander_name),
        )
        for commander in commanders:
            commander.cards.sort(key=lambda card: (-(card.yes + card.no), card.card_name))
            commander.cards = commander.cards[:10]

        return TrainingStatsResponse(
            total_votes=total_votes,
            commanders=commanders[:10],
        )
