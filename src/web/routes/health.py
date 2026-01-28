"""Health check routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
def health_check() -> dict[str, Any]:
    """Basic health check endpoint."""
    return {"status": "ok"}
