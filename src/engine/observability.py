"""Lightweight observability helpers for latency and cost estimation."""
from __future__ import annotations

import json
import logging
import math
import uuid
from typing import Any, Optional

logger = logging.getLogger("observability")


def estimate_tokens(text: str | None) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))

def log_event(event: str, payload: dict[str, Any], trace_id: Optional[str] = None) -> None:
    if trace_id:
        payload = dict(payload)
        payload["trace_id"] = trace_id
    logger.info("event=%s payload=%s", event, json.dumps(payload, sort_keys=True))


def generate_trace_id() -> str:
    return uuid.uuid4().hex
