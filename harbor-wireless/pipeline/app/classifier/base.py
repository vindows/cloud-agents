from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.jev import Question, SystemOneRequest, SystemOneResponse


class ClassifierBackend(ABC):
    name: str

    @abstractmethod
    async def systemone(self, request: SystemOneRequest) -> SystemOneResponse:
        raise NotImplementedError

    async def answer_questions(
        self, state: str, questions: dict[str, Question], model: str = "jev-latest"
    ) -> SystemOneResponse:
        return await self.systemone(
            SystemOneRequest(model=model, state=state, questions=questions)
        )
