"""Golden-set eval readout (label_* fields from data/golden-set.json)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from app.models.jev import ChoiceQuestion, NoulQuestion, ScoreQuestion
from app.models.tickets import TicketIn
from app.models.triage import ArchiveLeverConfig, TriageRequest
from app.store import store
from app.triage.engine import TriageEngine, _urgency_from_score

router = APIRouter(tags=["eval"])


@router.get("/eval/golden")
async def eval_golden(
    request: Request,
    limit: int = Query(default=200, ge=1, le=500),
    run_pipeline: bool = Query(
        default=False,
        description="If true, also run full triage (slower) for dedupe/parent checks.",
    ),
) -> dict[str, Any]:
    """Score classifier (and optionally pipeline) against golden-set labels."""
    classifier = request.app.state.classifier
    rows = store.golden[:limit]
    if not rows:
        return {
            "n": 0,
            "error": "golden-set.json not loaded; expected harbor-wireless/data/golden-set.json",
        }

    cat_correct = 0
    urg_correct = 0
    dup_correct = 0
    parent_correct = 0
    details: list[dict[str, Any]] = []

    engine = TriageEngine(
        classifier=classifier,
        agents_by_category=dict(store.agents_by_category),
    )

    for row in rows:
        text = f"{row.short_description}\n{row.description}".strip()
        resp = await classifier.answer_questions(
            state=text,
            questions={
                "category": ChoiceQuestion(
                    type="choice",
                    instructions="Which IT category does this ticket belong to?",
                    criteria={
                        "access": "Identity, passwords, MFA, permissions",
                        "hardware": "Laptops, monitors, peripherals",
                        "network": "WiFi, VPN, DNS, connectivity",
                        "applications": "Business apps, Outlook, Teams",
                    },
                ),
                "urgency": ScoreQuestion(
                    type="score",
                    instructions="How urgent is this IT ticket?",
                    criteria=[
                        "Can wait / low impact",
                        "Needs attention this week",
                        "Needs attention today / outage or blocked work",
                    ],
                ),
                "is_duplicate": NoulQuestion(
                    type="noul",
                    instructions="Is this a duplicate of an already-reported issue?",
                ),
            },
        )
        pred_cat = resp.answers["category"]["choice"]
        urg_score = float(resp.answers["urgency"]["score"])
        pred_urg = _urgency_from_score(urg_score)
        pred_dup = float(resp.answers["is_duplicate"]["noul"]) >= 0.5

        cat_ok = pred_cat == row.label_category
        urg_ok = pred_urg == row.label_urgency
        # Language-only noul is weak for dup; prefer pipeline when requested
        dup_ok = pred_dup == row.label_is_duplicate
        pred_parent: str | None = None

        if run_pipeline:
            # Compare against open corpus for structural dedupe
            result = await engine.run(
                TriageRequest(
                    ticket=TicketIn(
                        number=f"GOLD-{row.number}",
                        short_description=row.short_description,
                        description=row.description,
                        opened_at=row.opened_at,
                    ),
                    archive=ArchiveLeverConfig(mode="human", age_years=100),
                    existing_open=store.open_tickets(),
                    dry_run=True,
                )
            )
            pred_dup = result.outcome == "duplicate"
            dup_ok = pred_dup == row.label_is_duplicate
            pred_parent = result.ticket.parent
            if row.label_is_duplicate:
                if pred_parent == row.label_parent:
                    parent_correct += 1
            elif pred_parent is None:
                parent_correct += 1

        if cat_ok:
            cat_correct += 1
        if urg_ok:
            urg_correct += 1
        if dup_ok:
            dup_correct += 1

        details.append(
            {
                "number": row.number,
                "label_category": row.label_category,
                "pred_category": pred_cat,
                "label_urgency": row.label_urgency,
                "pred_urgency": pred_urg,
                "label_is_duplicate": row.label_is_duplicate,
                "pred_is_duplicate": pred_dup,
                "label_parent": row.label_parent,
                "pred_parent": pred_parent,
                "category_ok": cat_ok,
                "urgency_ok": urg_ok,
                "duplicate_ok": dup_ok,
            }
        )

    n = len(rows)
    out: dict[str, Any] = {
        "n": n,
        "run_pipeline": run_pipeline,
        "accuracy": {
            "category": cat_correct / n,
            "urgency": urg_correct / n,
            "is_duplicate": dup_correct / n,
        },
        "correct": {
            "category": cat_correct,
            "urgency": urg_correct,
            "is_duplicate": dup_correct,
        },
        "classifier_backend": classifier.name,
        "note": (
            "Labels use label_category / label_is_duplicate / label_urgency / "
            "label_parent from golden-set.json. parent is a ticket number."
        ),
    }
    if run_pipeline:
        out["accuracy"]["parent"] = parent_correct / n
        out["correct"]["parent"] = parent_correct
    # Keep response small by default
    out["sample_errors"] = [d for d in details if not (d["category_ok"] and d["urgency_ok"])][:15]
    return out
