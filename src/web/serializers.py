"""Shared serialization helpers for API routes."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.database.models import Card
from src.engine.context import summarize_context_config
from src.web.schemas import TrainingCard


def training_card_from_card(card: Card) -> TrainingCard:
    return TrainingCard(
        id=card.id,
        name=card.name,
        type_line=card.type_line,
        color_identity=card.color_identity or [],
        mana_cost=card.mana_cost,
        cmc=card.cmc,
        oracle_text=card.oracle_text,
        image_url=(card.image_uris or {}).get("normal") if card.image_uris else None,
        card_faces=card.card_faces,
    )


def serialize_agent_payload(agent) -> dict[str, Any]:
    return {
        "id": agent.agent_id,
        "display_name": agent.display_name,
        "type": agent.agent_type,
        "weight": agent.weight,
        "model": agent.model,
        "temperature": agent.temperature,
        "system_prompt": agent.system_prompt,
        "user_prompt_template": agent.user_prompt_template,
        "preferences": asdict(agent.preferences),
        "context": summarize_context_config(agent.context),
    }
