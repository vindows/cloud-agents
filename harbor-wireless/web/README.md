# Harbor Wireless — Signal Deck UI

CIO demo surfaces for Phase 1 auto-triage: live pipeline theater, ticket system, priority queue with assignment reasoning, ops dashboard, and archive levers.

Visual lock: **Direction A — Signal Deck** (`../docs/design/`).

## Run locally

```bash
cd harbor-wireless/web
npm install
npm run dev
```

Open http://127.0.0.1:5173

The Vite server exposes `../data` at `/demo-data` (6k tickets + 180 agents from the data worker). If that folder is missing, the UI falls back to a seeded demo subset.

Pipeline (optional, adapters fall back to local simulation):

```bash
cd harbor-wireless/pipeline
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

Optional env:

| Variable | Default | Purpose |
|---|---|---|
| `VITE_DATA_BASE` | `/demo-data` | Tickets/agents JSON base URL |
| `VITE_PIPELINE_URL` | `http://127.0.0.1:8080` | FastAPI triage/metrics/archive levers (`harbor-wireless/pipeline`) |

```bash
npm run build   # typecheck + production build
npm run preview # serve dist
```

## Surfaces

| Route | Job |
|---|---|
| `/` | Live triage — brand + 5-stage spine + reasoning |
| `/tickets` | Table list/detail |
| `/queue` | Ranked auto-assign with why |
| `/ops` | Handled metrics (≤3 hero figures) |
| `/policy` | Archive Auto / Human / Hybrid levers |

## Demo notes (operators)

- **Queue ranking** is UI-side (`buildQueue` from loaded tickets/agents). Phase 1 has no pipeline queue endpoint; live `/triage/run` remains the routing source of truth when the API is up.
- **Archive age math** uses a fixed demo “now” of `2026-11-24` so recency tiers stay stable across machines. Policy PUT still round-trips to `/archive/levers` when pipeline is running.
- **Client `applyArchivePolicy`** soft-mutates ticket triage labels for storytelling on load; re-run triage against the pipeline for authoritative outcomes.
