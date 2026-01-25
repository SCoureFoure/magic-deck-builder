"""Council analysis for training synergy cards."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Optional

from langchain_openai import ChatOpenAI

from src.config import settings
from src.database.models import Card, Commander
from src.engine.archetypes import compute_identity_from_deck, score_card_for_identity
from src.engine.council.config import load_council_config

def _normalize_score(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return value


def _budget_score(price_usd: Optional[float], price_cap: Optional[float]) -> float:
    if price_usd is None:
        return 0.5
    cap = price_cap or 20.0
    if cap <= 0:
        return 0.0
    return _normalize_score(1.0 - min(price_usd / cap, 1.0))


def _heuristic_opinion(
    card: Card,
    identity: Optional[dict[str, float]],
    preferences: dict[str, float],
) -> tuple[float, str]:
    theme_score = score_card_for_identity(card, identity) if identity else 0.5
    efficiency_score = _normalize_score(1.0 / (1.0 + max(card.cmc, 0.0)))
    budget_score = _budget_score(card.price_usd, preferences.get("price_cap_usd"))
    total_weight = (
        preferences.get("theme_weight", 0.5)
        + preferences.get("efficiency_weight", 0.25)
        + preferences.get("budget_weight", 0.25)
    )
    if total_weight <= 0:
        total_weight = 1.0
    weighted = (
        theme_score * preferences.get("theme_weight", 0.5)
        + efficiency_score * preferences.get("efficiency_weight", 0.25)
        + budget_score * preferences.get("budget_weight", 0.25)
    ) / total_weight
    summary = (
        f"theme={theme_score:.2f} efficiency={efficiency_score:.2f} budget={budget_score:.2f}"
    )
    return weighted, summary


def _build_reason_prompt(
    agent_id: str,
    commander: Commander,
    card: Card,
    preferences: dict[str, float],
    heuristic_score: float,
) -> tuple[str, str]:
    system_prompt = (
        "You are a council agent for Commander synergy training. "
        "Explain why the card is synergistic or not for the commander. "
        "Keep it short (1-2 sentences) and plain language."
    )
    user_prompt = (
        f"Agent ID: {agent_id}\n"
        f"Commander: {commander.card.name}\n"
        f"Commander text: {commander.card.oracle_text or ''}\n"
        f"Card: {card.name}\n"
        f"Card text: {card.oracle_text or ''}\n"
        f"Preferences: {preferences}\n"
        f"Heuristic score (0-1): {heuristic_score:.2f}\n"
        "Return only the reason text."
    )
    return system_prompt, user_prompt


def _llm_reason(
    agent_id: str,
    commander: Commander,
    card: Card,
    preferences: dict[str, float],
    heuristic_score: float,
    model: Optional[str],
    temperature: float,
    api_key_override: Optional[str],
) -> str:
    api_key = api_key_override or settings.openai_api_key
    if not api_key:
        return ""
    llm = ChatOpenAI(
        model=model or settings.openai_model,
        temperature=temperature,
        api_key=api_key,
    )
    system_prompt, user_prompt = _build_reason_prompt(
        agent_id,
        commander,
        card,
        preferences,
        heuristic_score,
    )
    response = llm.invoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    return getattr(response, "content", "").strip()


def council_training_opinions(
    commander: Commander,
    card: Card,
    config_path: Optional[str] = None,
    overrides: Optional[dict[str, object]] = None,
    api_key_override: Optional[str] = None,
) -> list[dict[str, object]]:
    config = load_council_config(
        config_path=None if config_path is None else Path(config_path),
        overrides=overrides,
    )
    identity = compute_identity_from_deck(commander.card, [card])

    opinions: list[dict[str, object]] = []
    for agent in config.agents:
        preferences = asdict(agent.preferences)
        heuristic_score, metrics = _heuristic_opinion(card, identity, preferences)
        reason = ""
        if agent.agent_type == "llm":
            reason = _llm_reason(
                agent.agent_id,
                commander,
                card,
                preferences,
                heuristic_score,
                agent.model,
                agent.temperature,
                api_key_override,
            )
        opinions.append(
            {
                "agent_id": agent.agent_id,
                "display_name": agent.display_name or agent.agent_id,
                "agent_type": agent.agent_type,
                "weight": agent.weight,
                "score": heuristic_score,
                "metrics": metrics,
                "reason": reason,
            }
        )

    return opinions
