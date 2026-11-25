"""TypeSafe hosted Jev backend — drop-in swap when CLASSIFIER_BACKEND=typesafe."""

from __future__ import annotations

import httpx

from app.classifier.base import ClassifierBackend
from app.config import Settings
from app.models.jev import SystemOneRequest, SystemOneResponse


class TypesafeClassifierBackend(ClassifierBackend):
    name = "typesafe"

    def __init__(self, settings: Settings) -> None:
        if not settings.typesafe_api_key:
            raise RuntimeError(
                "CLASSIFIER_BACKEND=typesafe requires TYPESAFE_API_KEY "
                "(or Settings.typesafe_api_key)."
            )
        self._settings = settings
        self._url = f"{settings.typesafe_base_url.rstrip('/')}/v1/systemone"

    async def systemone(self, request: SystemOneRequest) -> SystemOneResponse:
        payload = request.model_dump()
        if not payload.get("model"):
            payload["model"] = self._settings.typesafe_model
        headers = {
            "Authorization": f"Bearer {self._settings.typesafe_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(self._url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return SystemOneResponse.model_validate(data)
