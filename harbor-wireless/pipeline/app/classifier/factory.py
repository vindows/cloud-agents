from __future__ import annotations

from functools import lru_cache

from app.classifier.base import ClassifierBackend
from app.classifier.bert_backend import BertClassifierBackend
from app.classifier.typesafe_backend import TypesafeClassifierBackend
from app.config import Settings, get_settings


@lru_cache
def get_classifier(backend: str | None = None) -> ClassifierBackend:
    settings = get_settings()
    name = (backend or settings.classifier_backend).lower()
    if name == "bert":
        return BertClassifierBackend()
    if name == "typesafe":
        return TypesafeClassifierBackend(settings)
    raise ValueError(
        f"Unknown CLASSIFIER_BACKEND={name!r}; expected 'bert' or 'typesafe'."
    )


def reset_classifier_cache() -> None:
    get_classifier.cache_clear()


def build_classifier(settings: Settings | None = None) -> ClassifierBackend:
    """Non-cached builder (useful in tests)."""
    settings = settings or get_settings()
    if settings.classifier_backend == "bert":
        return BertClassifierBackend()
    if settings.classifier_backend == "typesafe":
        return TypesafeClassifierBackend(settings)
    raise ValueError(f"Unknown backend {settings.classifier_backend!r}")
