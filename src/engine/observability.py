"""Lightweight observability helpers for latency and cost estimation."""
from __future__ import annotations

import json
import logging
import math
from typing import Any

logger = logging.getLogger("observability")


def estimate_tokens(text: str | None) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def log_event(event: str, payload: dict[str, Any]) -> None:
    logger.info("event=%s payload=%s", event, json.dumps(payload, sort_keys=True))
