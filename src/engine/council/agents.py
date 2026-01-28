"""Council agent implementations."""
from __future__ import annotations

import json
from dataclasses import asdict
import time
from typing import Iterable, Optional

from langchain_openai import ChatOpenAI

from src.database.models import Card
from src.engine.archetypes import score_card_for_identity
from src.engine.context import CandidateContext, DeckContext, build_candidate_context, build_deck_context
from src.engine.observability import estimate_tokens, log_event
from src.engine.roles import classify_card_role, get_role_description
from src.engine.council.config import AgentConfig, AgentPreferences
from src.engine.validator import parse_agent_task
from src.config import settings


def _normalize_score(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return value


def _price_score(price_usd: Optional[float], preferences: AgentPreferences) -> float:
    if price_usd is None:
        return 0.5
    cap = preferences.price_cap_usd or 20.0
    if cap <= 0:
        return 0.0
    return _normalize_score(1.0 - min(price_usd / cap, 1.0))


def heuristic_rank_candidates(
    candidates: list[Card],
    role: str,
    identity: Optional[dict[str, float]],
    preferences: AgentPreferences,
) -> list[str]:
    scored: list[tuple[float, str]] = []
    for card in candidates:
        theme_score = score_card_for_identity(card, identity) if identity else 0.5
        efficiency_score = _normalize_score(1.0 / (1.0 + max(card.cmc, 0.0)))
        budget_score = _price_score(card.price_usd, preferences)
        role_bonus = 0.1 if classify_card_role(card) == role else 0.0

        total_weight = (
            preferences.theme_weight
            + preferences.efficiency_weight
            + preferences.budget_weight
        )
        if total_weight <= 0:
            total_weight = 1.0

        weighted = (
            theme_score * preferences.theme_weight
            + efficiency_score * preferences.efficiency_weight
            + budget_score * preferences.budget_weight
        ) / total_weight

        scored.append((weighted + role_bonus, card.name))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [name for _, name in scored]


def _build_llm_prompt(
    agent_id: str,
    role: str,
    deck_context: DeckContext,
    candidate_context: CandidateContext,
    preferences: AgentPreferences,
) -> tuple[str, str]:
    system_prompt = (
        "You are a Commander deckbuilding council agent. "
        "Follow the user preferences exactly. "
        "Return ONLY a JSON array of card names in ranked order, best to worst."
    )

    deck_list = ", ".join(deck_context.deck_cards)
    candidate_payload = candidate_context.payload

    user_prompt = (
        f"Agent ID: {agent_id}\n"
        f"Role needed: {role}\n"
        f"Role definition: {get_role_description(role)}\n"
        f"Commander: {deck_context.commander_name}\n"
        f"Commander text: {deck_context.commander_text}\n"
        f"Deck so far: {deck_list}\n"
        f"Preferences: {json.dumps(asdict(preferences))}\n"
        "Candidates (JSON list):\n"
        f"{json.dumps(candidate_payload)}\n"
        "Return ONLY a JSON array of card names."
    )

    return system_prompt, user_prompt


def _parse_ranked_names(text: str) -> list[str]:
    if not text:
        return []
    trimmed = text.strip()
    start = trimmed.find("[")
    end = trimmed.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        data = json.loads(trimmed[start : end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(item).strip() for item in data if isinstance(item, str) and item.strip()]


def llm_rank_candidates(
    agent: AgentConfig,
    role: str,
    commander_name: str,
    commander_text: str,
    deck_cards: list[Card],
    candidates: list[Card],
) -> list[str]:
    if not settings.openai_api_key:
        return []
    task, _ = parse_agent_task(
        {
            "role": role,
            "count": max(len(candidates), 1),
            "commander_name": commander_name,
            "commander_text": commander_text,
            "deck_cards": [card.name for card in deck_cards],
        }
    )
    if not task:
        return []

    deck_context = build_deck_context(task, agent.context)
    candidate_context = build_candidate_context(candidates, agent.context)

    model_name = agent.model or settings.openai_model
    llm = ChatOpenAI(
        model=model_name,
        temperature=agent.temperature,
        api_key=settings.openai_api_key,
    )

    system_prompt, user_prompt = _build_llm_prompt(
        agent.agent_id,
        role,
        deck_context,
        candidate_context,
        agent.preferences,
    )

    started = time.monotonic()
    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ])
    content = getattr(response, "content", "")
    duration_ms = int((time.monotonic() - started) * 1000)
    log_event(
        "council_llm_call",
        {
            "agent_id": agent.agent_id,
            "model": model_name,
            "role": role,
            "success": bool(content),
            "duration_ms": duration_ms,
            "prompt_tokens_est": estimate_tokens(system_prompt + user_prompt),
            "response_tokens_est": estimate_tokens(content),
        },
    )

    return _parse_ranked_names(content)
