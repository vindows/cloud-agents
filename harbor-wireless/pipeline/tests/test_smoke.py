from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.classifier.factory import reset_classifier_cache
from app.config import get_settings
from app.main import app
from app.normalize import coerce_ticket_dict, normalize_priority, normalize_state
from app.store import store

DATA_TICKETS = Path(__file__).resolve().parents[2] / "data" / "tickets.json"


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    monkeypatch.setenv("CLASSIFIER_BACKEND", "bert")
    get_settings.cache_clear()
    reset_classifier_cache()
    store.tickets.clear()
    store.results.clear()
    store._outcome_counts.clear()
    store._category_counts.clear()
    store._step_ms.clear()
    yield
    get_settings.cache_clear()
    reset_classifier_cache()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["classifier_backend"] == "bert"


def test_systemone_choice(client: TestClient):
    r = client.post(
        "/v1/systemone",
        json={
            "model": "jev-latest",
            "state": "Cannot login MFA lockout password reset needed",
            "questions": {
                "category": {
                    "type": "choice",
                    "instructions": "Which category?",
                    "criteria": {
                        "access": "passwords MFA identity",
                        "hardware": "laptop monitor",
                        "network": "wifi vpn",
                        "applications": "outlook teams",
                    },
                }
            },
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "answers" in data
    ans = data["answers"]["category"]
    assert ans["type"] == "choice"
    assert ans["choice"] == "access"
    assert 0 <= ans["confidence"] <= 1
    assert abs(sum(ans["probabilities"].values()) - 1.0) < 1e-5


def test_systemone_score_and_noul(client: TestClient):
    r = client.post(
        "/v1/systemone",
        json={
            "model": "jev-latest",
            "state": "Production VPN outage — all users down, critical ASAP",
            "questions": {
                "urgency": {
                    "type": "score",
                    "instructions": "How urgent?",
                    "criteria": [
                        "Can wait",
                        "Needs attention this week",
                        "Needs attention today",
                    ],
                },
                "is_outage": {
                    "type": "noul",
                    "instructions": "Is this describing a service outage?",
                },
            },
        },
    )
    assert r.status_code == 200
    answers = r.json()["answers"]
    assert answers["urgency"]["type"] == "score"
    assert answers["urgency"]["score"] >= 1.0
    assert answers["is_outage"]["type"] == "noul"
    assert 0 < answers["is_outage"]["noul"] < 1


def test_triage_run_routes_hardware(client: TestClient):
    r = client.post(
        "/triage/run",
        json={
            "ticket": {
                "short_description": "Laptop screen cracked",
                "description": "Need hardware replacement keyboard docking station",
                "caller_id": "u1",
            }
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["outcome"] in ("routed", "needs_human")
    steps = {s["step"] for s in body["steps"]}
    assert {"intake", "classify", "dedupe", "priority", "archive", "route"} <= steps
    for s in body["steps"]:
        assert s["reason"]
        assert 0 <= s["confidence"] <= 1
    assert body["ticket"]["category"] == "hardware"
    assert body["classifier_backend"] == "bert"


def test_triage_dedupe(client: TestClient):
    first = client.post(
        "/triage/run",
        json={
            "ticket": {
                "number": "INC1001",
                "short_description": "VPN tunnel drops every hour",
                "description": "Network connectivity VPN tunnel packet loss",
                "caller_id": "u2",
            }
        },
    ).json()
    assert first["outcome"] in ("routed", "needs_human")

    second = client.post(
        "/triage/run",
        json={
            "ticket": {
                "number": "INC1002",
                "short_description": "VPN tunnel drops every hour",
                "description": "Network connectivity VPN tunnel packet loss",
                "caller_id": "u2",
            }
        },
    ).json()
    assert second["outcome"] == "duplicate"
    assert second["ticket"]["duplicate_of"] == "INC1001"


def test_archive_levers_hybrid_auto(client: TestClient):
    client.put(
        "/archive/levers",
        json={"mode": "hybrid", "age_years": 3, "inactive_days": 365},
    )
    old = datetime.now(timezone.utc) - timedelta(days=int(4 * 365.25))
    inactive = datetime.now(timezone.utc) - timedelta(days=400)
    r = client.post(
        "/triage/run",
        json={
            "ticket": {
                "short_description": "Old printer offline",
                "description": "hardware printer offline years ago",
                "opened_at": old.isoformat(),
                "requester_last_active_at": inactive.isoformat(),
            }
        },
    )
    body = r.json()
    assert body["outcome"] == "archived"
    assert body["archive"]["auto_applied"] is True
    assert body["archive"]["mode"] == "hybrid"


def test_archive_levers_human(client: TestClient):
    client.put(
        "/archive/levers",
        json={"mode": "human", "age_years": 2, "inactive_days": 30},
    )
    old = datetime.now(timezone.utc) - timedelta(days=int(3 * 365.25))
    r = client.post(
        "/triage/run",
        json={
            "ticket": {
                "short_description": "Ancient access request",
                "description": "password reset access provisioning",
                "opened_at": old.isoformat(),
            }
        },
    )
    body = r.json()
    assert body["outcome"] == "archive_candidate"
    assert body["archive"]["needs_human"] is True
    assert body["archive"]["auto_applied"] is False


def test_metrics(client: TestClient):
    client.post(
        "/triage/run",
        json={
            "ticket": {
                "short_description": "Outlook crash on launch",
                "description": "applications outlook crash excel freeze",
            }
        },
    )
    r = client.get("/metrics")
    assert r.status_code == 200
    m = r.json()
    assert m["handled"] >= 1
    assert "outcomes" in m
    assert m["classifier_backend"] == "bert"


def test_normalize_servicenow_shapes():
    raw = {
        "short_description": "x",
        "priority": "3 - Moderate",
        "state": "New",
        "caller_id": {
            "sys_id": "abc",
            "name": "Pat",
            "user_name": "pat1",
            "active": False,
        },
        "assigned_to": {
            "sys_id": "def",
            "name": "Agent",
            "user_name": "agent1",
        },
        "parent": "INC1000527",
    }
    coerced = coerce_ticket_dict(raw)
    assert coerced["priority"] == "3 - Moderate"
    assert normalize_priority("3") == "3 - Moderate"
    assert normalize_state("in_progress") == "In Progress"
    assert coerced["state"] == "New"
    assert isinstance(coerced["caller_id"], dict)
    assert coerced["caller_id"]["user_name"] == "pat1"
    assert coerced["parent"] == "INC1000527"


def test_loads_real_dataset(client: TestClient):
    r = client.get("/health")
    body = r.json()
    assert body["tickets_loaded"] == 6000
    assert body["agents_loaded"] == 180
    assert body["golden_loaded"] == 200


def test_raw_tickets_json_triage_run(client: TestClient):
    """QA blocker: raw merged tickets.json must POST /triage/run without 422."""
    assert DATA_TICKETS.exists(), f"missing {DATA_TICKETS}"
    # Prefer an open-ish recent unique ticket to exercise route path
    tickets = json.loads(DATA_TICKETS.read_text())
    sample = next(
        t
        for t in tickets
        if t.get("state") == "New"
        and not t.get("is_duplicate")
        and t.get("recency_tier") == "recent"
    )
    # Ensure ServiceNow shapes still present (the 422 trigger)
    assert " - " in sample["priority"]
    assert sample["state"][0].isupper()
    assert isinstance(sample["caller_id"], dict)

    r = client.post("/triage/run", json={"ticket": sample, "dry_run": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["outcome"] in (
        "routed",
        "needs_human",
        "duplicate",
        "archived",
        "archive_candidate",
    )
    assert body["ticket"]["caller_id"]["user_name"] == sample["caller_id"]["user_name"]
    assert body["steps"]
    for step in body["steps"]:
        assert step["reason"]
        assert 0 <= step["confidence"] <= 1


def test_triage_parent_is_ticket_number(client: TestClient):
    client.post(
        "/triage/run",
        json={
            "ticket": {
                "number": "INC9001",
                "short_description": "Cannot reset AD password after lockout",
                "description": "access identity MFA password reset SSO",
                "caller_id": {"user_name": "same.user", "active": True},
            }
        },
    )
    dup = client.post(
        "/triage/run",
        json={
            "ticket": {
                "number": "INC9002",
                "short_description": "Cannot reset AD password after lockout",
                "description": "access identity MFA password reset SSO",
                "caller_id": {"user_name": "same.user", "active": True},
            }
        },
    ).json()
    assert dup["outcome"] == "duplicate"
    assert dup["ticket"]["parent"] == "INC9001"
    assert dup["ticket"]["duplicate_of"] == "INC9001"


def test_golden_eval_endpoint(client: TestClient):
    r = client.get("/eval/golden?limit=20")
    assert r.status_code == 200
    body = r.json()
    assert body["n"] == 20
    assert "accuracy" in body
    assert "category" in body["accuracy"]
    assert body["accuracy"]["category"] >= 0.3  # demo classifier floor
