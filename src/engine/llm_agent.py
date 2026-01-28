"""LLM-assisted card suggestion agent (structured search + ranking)."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from typing import Iterable, Optional

import httpx
from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.config import settings
from src.database.models import Card, Commander, LLMRun
from src.engine.brief import AgentTask, SearchQuery
from src.engine.context import (
    AgentContextConfig,
    SourceAttribution,
    build_candidate_context,
    build_deck_context,
    summarize_context_config,
)
from src.engine.observability import estimate_tokens, log_event
from src.engine.roles import classify_card_role, get_role_description
from src.engine.text_vectorizer import compute_similarity
from src.engine.validator import parse_agent_task

logger = logging.getLogger(__name__)


def build_search_prompt(
    request: AgentTask, context_config: AgentContextConfig | None = None
) -> str:
    """Build a strict JSON-only prompt for search queries."""
    config = context_config or AgentContextConfig()
    deck_context = build_deck_context(request, config)
    deck_list = ", ".join(deck_context.deck_cards)
    return (
        "You are a Commander deckbuilding assistant.\n"
        "Return ONLY a JSON array of search objects, with no extra text.\n"
        "Each object must use these keys: oracle_contains (list), type_contains (list), "
        "cmc_min (number or null), cmc_max (number or null), colors (list).\n\n"
        f"Role definition: {get_role_description(request.role)}\n"
        f"Commander: {deck_context.commander_name}\n"
        f"Commander text: {deck_context.commander_text}\n"
        f"Deck so far (names): {deck_list}\n"
        f"Role needed: {request.role}\n"
        f"Count: {request.count}\n"
    )


def build_ranking_prompt(
    request: AgentTask,
    candidates: list[Card],
    context_config: AgentContextConfig | None = None,
) -> str:
    """Build a strict JSON-only prompt for ranking card names."""
    config = context_config or AgentContextConfig()
    deck_context = build_deck_context(request, config)
    candidate_context = build_candidate_context(candidates, config)
    deck_list = ", ".join(deck_context.deck_cards)
    candidate_list = ", ".join(card.name for card in candidate_context.candidates)
    return (
        "You are a Commander deckbuilding assistant.\n"
        "Return ONLY a JSON array of card names (strings), ordered best to worst.\n\n"
        f"Role definition: {get_role_description(request.role)}\n"
        f"Commander: {deck_context.commander_name}\n"
        f"Commander text: {deck_context.commander_text}\n"
        f"Deck so far (names): {deck_list}\n"
        f"Role needed: {request.role}\n"
        f"Candidates: {candidate_list}\n"
        f"Count: {request.count}\n"
    )


def parse_card_names(response_text: str) -> list[str]:
    """Parse JSON array of card names from LLM output."""
    if not response_text:
        return []
    text = response_text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [name for name in data if isinstance(name, str) and name.strip()]


def parse_search_queries(response_text: str) -> list[SearchQuery]:
    """Parse JSON array of search queries from LLM output."""
    if not response_text:
        logger.info("LLM search response empty.")
        return []
    text = response_text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        logger.info("LLM search response JSON parse failed.")
        return []
    if not isinstance(data, list):
        return []

    queries: list[SearchQuery] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            queries.append(SearchQuery(**item))
        except ValidationError:
            continue
    return queries


def _call_openai(prompt: str, system_prompt: str, temperature: float) -> str | None:
    if not settings.openai_api_key:
        return None

    started = time.monotonic()
    payload = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        duration_ms = int((time.monotonic() - started) * 1000)
        log_event(
            "llm_call",
            {
                "model": settings.openai_model,
                "success": False,
                "duration_ms": duration_ms,
                "prompt_tokens_est": estimate_tokens(system_prompt + prompt),
            },
        )
        return None

    data = response.json()
    content = data["choices"][0]["message"]["content"]
    duration_ms = int((time.monotonic() - started) * 1000)
    log_event(
        "llm_call",
        {
            "model": settings.openai_model,
            "success": True,
            "duration_ms": duration_ms,
            "prompt_tokens_est": estimate_tokens(system_prompt + prompt),
            "response_tokens_est": estimate_tokens(content),
        },
    )
    return content


def _log_llm_run(
    session: Session,
    deck_id: int,
    commander_id: int,
    role: str,
    model: str,
    prompt: str,
    response: Optional[str],
    success: bool,
) -> None:
    llm_run = LLMRun(
        deck_id=deck_id,
        commander_id=commander_id,
        role=role,
        model=model,
        prompt=prompt,
        response=response,
        success=success,
    )
    session.add(llm_run)
    session.flush()


def _search_cards(
    session: Session,
    query: SearchQuery,
    commander_colors: set[str],
    exclude_ids: set[int],
    limit: int,
) -> list[Card]:
    db_query = session.query(Card)
    for text in query.oracle_contains:
        db_query = db_query.filter(Card.oracle_text.ilike(f"%{text}%"))
    for text in query.type_contains:
        db_query = db_query.filter(Card.type_line.ilike(f"%{text}%"))
    if query.cmc_min is not None:
        db_query = db_query.filter(Card.cmc >= query.cmc_min)
    if query.cmc_max is not None:
        db_query = db_query.filter(Card.cmc <= query.cmc_max)

    results: list[Card] = []
    for card in db_query.limit(limit).all():
        if card.id in exclude_ids:
            continue
        if card.legalities.get("commander") != "legal":
            continue
        card_colors = set(card.color_identity or [])
        if not card_colors.issubset(commander_colors):
            continue
        if query.colors and not set(query.colors).issubset(commander_colors):
            continue
        results.append(card)
    return results


def _suggest_cards_for_role(
    session: Session,
    deck_id: int,
    commander: Commander,
    deck_cards: Iterable[Card],
    role: str,
    count: int,
    exclude_ids: set[int],
    context_config: AgentContextConfig | None = None,
) -> tuple[list[Card], list[SourceAttribution]]:
    """Suggest cards via LLM search + ranking, then validate against database and role."""
    context_config = context_config or AgentContextConfig()
    commander_card = commander.card
    deck_names = [card.name for card in deck_cards if card.id not in exclude_ids]
    task, task_errors = parse_agent_task(
        {
            "role": role,
            "count": count,
            "commander_name": commander_card.name,
            "commander_text": commander_card.oracle_text or "",
            "deck_cards": deck_names,
        }
    )
    if not task:
        logger.info("LLM request invalid: role=%s errors=%s", role, task_errors)
        return [], []

    logger.info(
        "LLM context config: role=%s config=%s",
        role,
        json.dumps(summarize_context_config(context_config)),
    )

    search_prompt = build_search_prompt(task, context_config)

    logger.info("LLM search start: role=%s count=%s commander=%s", role, count, commander_card.name)
    search_response = _call_openai(
        search_prompt,
        system_prompt=(
            "You produce structured search queries for Commander deckbuilding.\n"
            "Return JSON only. Avoid commentary. Ensure queries align with the role and commander."
        ),
        temperature=0.6,
    )
    _log_llm_run(
        session=session,
        deck_id=deck_id,
        commander_id=commander.id,
        role=f"{role}:search",
        model=settings.openai_model,
        prompt=search_prompt,
        response=search_response,
        success=bool(search_response),
    )

    queries = parse_search_queries(search_response or "")
    logger.info("LLM search parsed queries: role=%s queries=%s", role, len(queries))
    if not queries:
        return [], []

    commander_colors = set(commander.color_identity or [])
    candidates: list[Card] = []
    seen_ids: set[int] = set()
    source_attributions: list[SourceAttribution] = []
    max_attribution_cards = min(context_config.budget.max_candidates, 100)
    for query in queries:
        results = _search_cards(
            session=session,
            query=query,
            commander_colors=commander_colors,
            exclude_ids=exclude_ids,
            limit=50,
        )
        if results:
            source_attributions.append(
                SourceAttribution(
                    source_type="llm_search_query",
                    details={"query": asdict(query)},
                    card_ids=[card.id for card in results[:max_attribution_cards]],
                    card_names=[card.name for card in results[:max_attribution_cards]],
                )
            )
        for card in results:
            if card.id in seen_ids:
                continue
            seen_ids.add(card.id)
            candidates.append(card)

    logger.info("LLM search candidates: role=%s candidates=%s", role, len(candidates))
    if not candidates:
        return [], []

    candidate_context = build_candidate_context(candidates, context_config)
    if source_attributions:
        logger.info(
            "LLM candidate sources: role=%s sources=%s",
            role,
            json.dumps([asdict(item) for item in source_attributions]),
        )

    rank_prompt = build_ranking_prompt(task, candidate_context.candidates, context_config)
    rank_response = _call_openai(
        rank_prompt,
        system_prompt=(
            "You rank candidate cards for a Commander deck role.\n"
            "Return JSON only. Order from best fit to worst."
        ),
        temperature=0.2,
    )
    _log_llm_run(
        session=session,
        deck_id=deck_id,
        commander_id=commander.id,
        role=f"{role}:rank",
        model=settings.openai_model,
        prompt=rank_prompt,
        response=rank_response,
        success=bool(rank_response),
    )

    ranked_names = parse_card_names(rank_response or "")
    logger.info("LLM rank parsed names: role=%s names=%s", role, len(ranked_names))
    name_to_card = {card.name: card for card in candidate_context.candidates}
    ranked_candidates = [name_to_card[name] for name in ranked_names if name in name_to_card]
    if not ranked_candidates:
        ranked_candidates = candidate_context.candidates
    else:
        similarities = compute_similarity(session, commander_card, ranked_candidates)
        rank_weight = max(len(ranked_names), 1)
        name_rank = {name: idx for idx, name in enumerate(ranked_names)}
        ranked_candidates = sorted(
            ranked_candidates,
            key=lambda card: (
                -(
                    0.7 * (1 - (name_rank.get(card.name, rank_weight) / rank_weight))
                    + 0.3 * similarities.get(card.id, 0.0)
                ),
                card.name,
            ),
        )

    selected: list[Card] = []
    for card in ranked_candidates:
        if card.id in exclude_ids:
            continue
        if classify_card_role(card) != role:
            continue
        selected.append(card)
        if len(selected) >= count:
            break

    logger.info("LLM selected cards: role=%s selected=%s", role, len(selected))
    if selected:
        session.query(LLMRun).filter(
            LLMRun.deck_id == deck_id, LLMRun.role == f"{role}:rank"
        ).update({"success": True})

    return selected, source_attributions


def suggest_cards_for_role(
    session: Session,
    deck_id: int,
    commander: Commander,
    deck_cards: Iterable[Card],
    role: str,
    count: int,
    exclude_ids: set[int],
    context_config: AgentContextConfig | None = None,
) -> list[Card]:
    """Suggest cards via LLM search + ranking, then validate against database and role."""
    selected, _ = _suggest_cards_for_role(
        session=session,
        deck_id=deck_id,
        commander=commander,
        deck_cards=deck_cards,
        role=role,
        count=count,
        exclude_ids=exclude_ids,
        context_config=context_config,
    )
    return selected


def suggest_cards_with_attribution(
    session: Session,
    deck_id: int,
    commander: Commander,
    deck_cards: Iterable[Card],
    role: str,
    count: int,
    exclude_ids: set[int],
    context_config: AgentContextConfig | None = None,
) -> tuple[list[Card], list[SourceAttribution]]:
    """Suggest cards and return attribution details for the selection."""
    return _suggest_cards_for_role(
        session=session,
        deck_id=deck_id,
        commander=commander,
        deck_cards=deck_cards,
        role=role,
        count=count,
        exclude_ids=exclude_ids,
        context_config=context_config,
    )
