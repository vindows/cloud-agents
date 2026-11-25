from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.classifier.factory import get_classifier
from app.config import get_settings
from app.routes import eval_golden, metrics, systemone, triage
from app.store import resolve_data_dir, store


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.classifier = get_classifier(settings.classifier_backend)
    data_dir = resolve_data_dir(settings.data_dir)
    counts = store.load_data_dir(data_dir)
    app.state.data_dir = str(data_dir)
    app.state.data_counts = counts
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
app.include_router(eval_golden.router)


@app.get("/health")
async def health():
    settings = get_settings()
    return {
        "ok": True,
        "version": __version__,
        "classifier_backend": settings.classifier_backend,
        "data_dir": getattr(app.state, "data_dir", None),
        "tickets_loaded": store.tickets_loaded,
        "agents_loaded": store.agents_loaded,
        "golden_loaded": store.golden_loaded,
    }
