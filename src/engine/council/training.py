"""Council analysis for training synergy cards."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Optional

import time

from langchain_openai import ChatOpenAI

from src.config import settings
from src.database.models import Card, Commander
from src.engine.archetypes import compute_identity_from_deck, score_card_for_identity
from src.engine.council.config import AgentConfig, load_council_config
from src.engine.observability import estimate_tokens, log_event

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


DEFAULT_SYSTEM_PROMPT = (
    "You are a council agent for Commander synergy training. "
    "Explain why the card is synergistic or not for the commander and if it would be "
    "a no or if it has potential. "
    "Keep it short (1-2 sentences) and plain language."
)
DEFAULT_USER_PROMPT = (
    "Explain in 1-2 sentences whether this card has synergy with the commander. "
    "Use the data provided and return only the reason text."
)


def _build_data_block(
    agent: AgentConfig,
    commander: Commander,
    card: Card,
    preferences: dict[str, float],
    heuristic_score: float,
) -> str:
    return (
        "Data:\n"
        f"Agent ID: {agent.agent_id}\n"
        f"Commander: {commander.card.name}\n"
        f"Commander text: {commander.card.oracle_text or ''}\n"
        f"Card: {card.name}\n"
        f"Card text: {card.oracle_text or ''}\n"
        f"Preferences: {preferences}\n"
        f"Heuristic score (0-1): {heuristic_score:.2f}"
    )


def _build_synthesis_block(
    opinions: list[dict[str, object]],
) -> str:
    lines = ["Council opinions:"]
    for opinion in opinions:
        agent_id = opinion.get("agent_id", "")
        agent_type = opinion.get("agent_type", "")
        weight = opinion.get("weight", 1.0)
        score = opinion.get("score", 0.0)
        metrics = opinion.get("metrics", "")
        reason = opinion.get("reason", "")
        lines.append(
            f"- {agent_id} ({agent_type}) weight={weight} score={score} metrics={metrics} reason={reason}"
        )
    return "\n".join(lines)


def _build_reason_prompt(
    agent: AgentConfig,
    commander: Commander,
    card: Card,
    preferences: dict[str, float],
    heuristic_score: float,
) -> tuple[str, str]:
    system_prompt = agent.system_prompt or DEFAULT_SYSTEM_PROMPT
    template = agent.user_prompt_template or DEFAULT_USER_PROMPT
    data_block = _build_data_block(agent, commander, card, preferences, heuristic_score)
    user_prompt = f"{template}\n\n{data_block}"
    return system_prompt, user_prompt


def _llm_reason(
    agent: AgentConfig,
    commander: Commander,
    card: Card,
    preferences: dict[str, float],
    heuristic_score: float,
    model: Optional[str],
    temperature: float,
    api_key_override: Optional[str],
    trace_id: Optional[str],
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
        agent,
        commander,
        card,
        preferences,
        heuristic_score,
    )
    started = time.monotonic()
    response = llm.invoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    content = getattr(response, "content", "").strip()
    duration_ms = int((time.monotonic() - started) * 1000)
    log_event(
        "training_llm_reason",
        {
            "agent_id": agent.agent_id,
            "model": model or settings.openai_model,
            "success": bool(content),
            "duration_ms": duration_ms,
            "prompt_tokens_est": estimate_tokens(system_prompt + user_prompt),
            "response_tokens_est": estimate_tokens(content),
        },
        trace_id=trace_id,
    )
    return content


def council_training_opinions(
    commander: Commander,
    card: Card,
    config_path: Optional[str] = None,
    overrides: Optional[dict[str, object]] = None,
    api_key_override: Optional[str] = None,
    trace_id: Optional[str] = None,
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
                agent,
                commander,
                card,
                preferences,
                heuristic_score,
                agent.model,
                agent.temperature,
                api_key_override,
                trace_id,
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


def council_training_synthesis(
    commander: Commander,
    card: Card,
    opinions: list[dict[str, object]],
    synthesizer: AgentConfig,
    api_key_override: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> str:
    api_key = api_key_override or settings.openai_api_key
    if not api_key:
        return ""
    llm = ChatOpenAI(
        model=synthesizer.model or settings.openai_model,
        temperature=synthesizer.temperature,
        api_key=api_key,
    )
    system_prompt = synthesizer.system_prompt or DEFAULT_SYSTEM_PROMPT
    user_prompt = (synthesizer.user_prompt_template or DEFAULT_USER_PROMPT).strip()
    data_block = _build_synthesis_block(opinions)
    combined_prompt = f"{user_prompt}\n\n{data_block}"
    started = time.monotonic()
    response = llm.invoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": combined_prompt},
        ]
    )
    content = getattr(response, "content", "").strip()
    duration_ms = int((time.monotonic() - started) * 1000)
    log_event(
        "training_llm_synthesis",
        {
            "agent_id": synthesizer.agent_id,
            "model": synthesizer.model or settings.openai_model,
            "success": bool(content),
            "duration_ms": duration_ms,
            "prompt_tokens_est": estimate_tokens(system_prompt + combined_prompt),
            "response_tokens_est": estimate_tokens(content),
        },
        trace_id=trace_id,
    )
    return content
