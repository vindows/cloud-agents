# Publishing Signal Deck (Cursor publish-app)

Standalone SPA for phone/live demos. Full ~6k ticket dataset ships in the static build; pipeline is optional.

## Local production preview

```bash
cd harbor-wireless/web
npm install
npm run build    # copies ../data → public/demo-data, then vite build
npm run preview  # http://127.0.0.1:4173
```

Confirm dataset in the build:

```bash
test -f dist/demo-data/tickets.json && ls -lh dist/demo-data/
```

Refresh demo JSON without a full build:

```bash
npm run copy-demo-data
```

## Cursor publish-app

1. Publish project dir: `harbor-wireless/web` (contains `package.json` + Vite app).
2. Host runs `npm install` / `npm run build`. `prebuild` copies `../data/*.json` into `public/demo-data/` when the sibling data folder is present; committed `public/demo-data/` is the fallback if packing only ships `web/`.
3. No `VITE_PIPELINE_URL` needed. In production builds, a localhost pipeline URL is ignored so the SPA does not hang waiting on `127.0.0.1:8080`. Triage uses client-side `simulateTriage`; metrics/queue/policy use seed adapters.
4. Optional: point `VITE_PIPELINE_URL` at a publicly reachable pipeline host if you want live `/triage/run` + `/metrics`.

## Dev (full stack)

```bash
# UI — Vite middleware serves ../data at /demo-data
cd harbor-wireless/web && npm run dev

# Optional pipeline
cd harbor-wireless/pipeline
uvicorn app.main:app --reload --port 8080
```

## Notes

- `tickets.json` is ~5 MiB (6 000 rows) — practical for static hosting.
- Seed fallback (~180 tickets) only applies if `/demo-data/tickets.json` is missing.
- Do not rely on Tailscale or loopback pipeline URLs for phone demos.
