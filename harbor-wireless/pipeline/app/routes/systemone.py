from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.models.jev import SystemOneRequest, SystemOneResponse

router = APIRouter(tags=["systemone"])


@router.post("/v1/systemone", response_model=SystemOneResponse)
async def systemone(body: SystemOneRequest, request: Request) -> SystemOneResponse:
    """Jev-compatible System One shim.

    Backend selected by CLASSIFIER_BACKEND=bert|typesafe.
    """
    classifier = request.app.state.classifier
    try:
        return await classifier.systemone(body)
    except Exception as exc:  # noqa: BLE001 — surface as 502 for upstream failures
        raise HTTPException(status_code=502, detail=str(exc)) from exc
