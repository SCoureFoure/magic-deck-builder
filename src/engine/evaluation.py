"""Evaluation harness for golden task runs."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.config import settings
from src.database.seed_roles import seed_roles
from src.engine.archetypes import compute_identity_from_deck
from src.engine.commander import create_commander_entry, find_commanders
from src.engine.deck_builder import generate_deck
from src.engine.metrics import compute_coherence_metrics
from src.engine.validator import validate_deck


@dataclass(frozen=True)
class GoldenTask:
    commander_name: str
    use_llm_agent: bool = False
    use_council: bool = False
    council_config_path: Optional[str] = None
    council_overrides: Optional[dict[str, Any]] = None
    expected_total_cards: int = 100
    requires_llm: Optional[bool] = None


@dataclass(frozen=True)
class GoldenResult:
    task: GoldenTask
    success: bool
    duration_ms: int
    total_cards: int = 0
    validation_errors: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


def load_golden_tasks(path: Path) -> list[GoldenTask]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    tasks: list[GoldenTask] = []
    if not isinstance(data, list):
        return tasks
    for item in data:
        if not isinstance(item, dict):
            continue
        tasks.append(
            GoldenTask(
                commander_name=str(item.get("commander_name", "")).strip(),
                use_llm_agent=bool(item.get("use_llm_agent", False)),
                use_council=bool(item.get("use_council", False)),
                council_config_path=item.get("council_config_path"),
                council_overrides=item.get("council_overrides"),
                expected_total_cards=int(item.get("expected_total_cards", 100)),
                requires_llm=item.get("requires_llm"),
            )
        )
    return [task for task in tasks if task.commander_name]


def _requires_llm(task: GoldenTask) -> bool:
    if task.requires_llm is not None:
        return task.requires_llm
    return task.use_llm_agent or task.use_council


def run_golden_tasks(
    session: Session, tasks: list[GoldenTask]
) -> list[GoldenResult]:
    results: list[GoldenResult] = []
    seed_roles(session)
    for task in tasks:
        if _requires_llm(task) and not settings.openai_api_key:
            results.append(
                GoldenResult(
                    task=task,
                    success=False,
                    duration_ms=0,
                    error="Skipped (OPENAI_API_KEY not set)",
                )
            )
            continue

        started = time.monotonic()
        try:
            commanders = find_commanders(session, name_query=task.commander_name, limit=1)
            if not commanders:
                results.append(
                    GoldenResult(
                        task=task,
                        success=False,
                        duration_ms=0,
                        error=f"Commander not found: {task.commander_name}",
                    )
                )
                continue

            commander_card = commanders[0]
            commander = create_commander_entry(session, commander_card)
            if not commander:
                results.append(
                    GoldenResult(
                        task=task,
                        success=False,
                        duration_ms=0,
                        error=f"Commander entry failed: {task.commander_name}",
                    )
                )
                continue

            deck = generate_deck(
                session,
                commander,
                constraints={
                    "use_llm_agent": task.use_llm_agent,
                    "use_council": task.use_council,
                    "council_config_path": task.council_config_path,
                    "council_overrides": task.council_overrides,
                },
            )

            is_valid, errors = validate_deck(deck)
            total_cards = sum(dc.quantity for dc in deck.deck_cards)
            nonland_cards = [
                dc.card
                for dc in deck.deck_cards
                if dc.card.type_line and "land" not in dc.card.type_line.lower()
            ]
            deck_identity = compute_identity_from_deck(commander_card, nonland_cards)
            metrics = compute_coherence_metrics(deck, deck_identity)
            duration_ms = int((time.monotonic() - started) * 1000)

            success = is_valid and total_cards == task.expected_total_cards
            results.append(
                GoldenResult(
                    task=task,
                    success=success,
                    duration_ms=duration_ms,
                    total_cards=total_cards,
                    validation_errors=errors,
                    metrics=metrics,
                )
            )
        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            results.append(
                GoldenResult(
                    task=task,
                    success=False,
                    duration_ms=duration_ms,
                    error=str(exc),
                )
            )
    return results


def write_results(path: Path, results: list[GoldenResult]) -> None:
    payload = [asdict(result) for result in results]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
