from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ClassifierBackend = Literal["bert", "typesafe"]
ArchiveMode = Literal["auto", "human", "hybrid"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    classifier_backend: ClassifierBackend = "bert"
    typesafe_api_key: str | None = None
    typesafe_base_url: str = "https://api.typesafe.ai"
    typesafe_model: str = "jev-latest"

    # Archive policy defaults (overridable via API)
    archive_mode: ArchiveMode = "hybrid"
    archive_age_years: float = 3.0
    archive_inactive_days: int = 365

    # Low-confidence HITL threshold
    confidence_threshold: float = 0.55

    data_dir: str = "../data"
    host: str = "0.0.0.0"
    port: int = 8080


@lru_cache
def get_settings() -> Settings:
    return Settings()
