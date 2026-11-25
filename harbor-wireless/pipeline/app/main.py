from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.classifier.factory import get_classifier
from app.config import get_settings
from app.routes import metrics, systemone, triage
from app.store import store


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.classifier = get_classifier(settings.classifier_backend)
    data_dir = Path(settings.data_dir)
    if not data_dir.is_absolute():
        # Relative to harbor-wireless/pipeline/
        data_dir = Path(__file__).resolve().parents[2] / "data"
    loaded = store.load_tickets_file(data_dir / "tickets.json")
    app.state.tickets_loaded = loaded
    yield


app = FastAPI(
    title="Harbor Wireless Triage Pipeline",
    description=(
        "Visible Phase-1 auto-triage: Jev-compatible /v1/systemone shim with "
        "BERT (or TypeSafe) behind it, plus classify → dedupe → priority → "
        "route/archive with step reasons and archive levers."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(systemone.router)
app.include_router(triage.router)
app.include_router(metrics.router)


@app.get("/health")
async def health():
    settings = get_settings()
    return {
        "ok": True,
        "version": __version__,
        "classifier_backend": settings.classifier_backend,
        "tickets_loaded": getattr(app.state, "tickets_loaded", 0),
    }
