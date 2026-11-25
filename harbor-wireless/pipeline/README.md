# Harbor Wireless — Visible Triage Pipeline

FastAPI service that runs Phase-1 auto-triage on ServiceNow-shaped tickets with every step visible for the CIO demo.

## What it does

1. **`POST /v1/systemone`** — Jev-compatible System One shim (`choice` | `score` | `noul`)
2. **Classifier backends** (swap via env, no client rewrite):
   - `CLASSIFIER_BACKEND=bert` (default) — lightweight TF-IDF + logistic intent model
   - `CLASSIFIER_BACKEND=typesafe` — hosted TypeSafe Jev (`TYPESAFE_API_KEY` required)
3. **`POST /triage/run`** — full pipeline: intake → classify → dedupe → priority → route **or** archive-candidate  
   Every step returns `reason` + `confidence` (+ optional `needs_human`)
4. **Archive levers** — `auto` | `human` | `hybrid` (age + inactive requester)
5. **`GET /metrics`** — ops dashboard counters from handled tickets

## Quick start

```bash
cd harbor-wireless/pipeline
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Default: local BERT-style backend
uvicorn app.main:app --reload --port 8080
```

Health check: `GET http://127.0.0.1:8080/health`

### TypeSafe swap

```bash
export CLASSIFIER_BACKEND=typesafe
export TYPESAFE_API_KEY=sk-...
uvicorn app.main:app --port 8080
```

## Example: System One classify

```bash
curl -s http://127.0.0.1:8080/v1/systemone -H 'Content-Type: application/json' -d '{
  "model": "jev-latest",
  "state": "Cannot login — MFA lockout on my VPN account",
  "questions": {
    "category": {
      "type": "choice",
      "instructions": "Which IT category?",
      "criteria": {
        "access": "Identity, passwords, MFA",
        "hardware": "Laptops and peripherals",
        "network": "WiFi, VPN, connectivity",
        "applications": "Business apps and installs"
      }
    }
  }
}' | jq
```

## Example: run triage

```bash
curl -s http://127.0.0.1:8080/triage/run -H 'Content-Type: application/json' -d '{
  "ticket": {
    "short_description": "Laptop screen cracked after travel",
    "description": "Need hardware replacement for docking and monitor issues",
    "caller_id": "user.123"
  }
}' | jq
```

## Archive levers

```bash
# Read current policy
curl -s http://127.0.0.1:8080/archive/levers | jq

# Hybrid: auto-archive only if age >= 3y AND requester inactive 365d
curl -s -X PUT http://127.0.0.1:8080/archive/levers \
  -H 'Content-Type: application/json' \
  -d '{"mode":"hybrid","age_years":3,"inactive_days":365}' | jq

# Fully automatic / human-approve-all
# {"mode":"auto", ...}  or  {"mode":"human", ...}
```

Modes:

| Mode | Behavior |
|------|----------|
| `auto` | Archive when ticket age ≥ `age_years` |
| `human` | Always surface candidates for approval (never auto-apply) |
| `hybrid` | Auto only when age ≥ `age_years` **and** requester inactive ≥ `inactive_days` |

## Metrics

```bash
curl -s http://127.0.0.1:8080/metrics | jq
```

## Data

On startup the app optionally loads `harbor-wireless/data/tickets.json` (produced by the data workstream). If missing, triage still works — pass `existing_open` in the request body or run against an empty open set.

## Layout

```
pipeline/
  app/
    main.py              # FastAPI entry
    config.py            # CLASSIFIER_BACKEND, archive defaults
    classifier/          # bert | typesafe backends
    triage/              # engine + archive policy
    routes/              # /v1/systemone, /triage/run, /metrics, /archive/levers
    models/              # Jev + ticket + pipeline schemas
  requirements.txt
  README.md
```

## Tests

```bash
pip install -r requirements.txt
python -m pytest tests/ -q
```
