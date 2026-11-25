from __future__ import annotations

from fastapi import APIRouter, Request

from app.models.triage import (
    ArchiveLeverConfig,
    PipelineResult,
    TriageRequest,
)
from app.store import store
from app.triage.engine import TriageEngine

router = APIRouter(tags=["triage"])


@router.post("/triage/run", response_model=PipelineResult)
async def triage_run(body: TriageRequest, request: Request) -> PipelineResult:
    """Run full classify → dedupe → priority → route|archive pipeline."""
    classifier = request.app.state.classifier
    engine = TriageEngine(classifier)
    levers = body.archive or store.get_archive_levers()
    req = TriageRequest(
        ticket=body.ticket,
        archive=levers,
        existing_open=body.existing_open
        if body.existing_open is not None
        else store.open_tickets(),
        dry_run=body.dry_run,
    )
    result = await engine.run(req)
    if not body.dry_run:
        store.record_result(result)
    return result


@router.get("/archive/levers", response_model=ArchiveLeverConfig)
async def get_archive_levers() -> ArchiveLeverConfig:
    return store.get_archive_levers()


@router.put("/archive/levers", response_model=ArchiveLeverConfig)
async def put_archive_levers(body: ArchiveLeverConfig) -> ArchiveLeverConfig:
    """Set archive mode: auto | human | hybrid (+ age / inactive thresholds)."""
    return store.set_archive_levers(body)
