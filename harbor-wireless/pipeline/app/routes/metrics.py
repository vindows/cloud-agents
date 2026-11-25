from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.store import store

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics() -> dict[str, Any]:
    """Ops dashboard metrics from handled tickets."""
    return store.metrics()
