"""Jev / System One compatible request and response shapes."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class ChoiceQuestion(BaseModel):
    type: Literal["choice"] = "choice"
    instructions: str
    criteria: dict[str, str]


class ScoreQuestion(BaseModel):
    type: Literal["score"] = "score"
    instructions: str
    criteria: list[str]


class NoulQuestion(BaseModel):
    type: Literal["noul"] = "noul"
    instructions: str
    criteria: dict[str, str] | None = None


Question = Annotated[
    ChoiceQuestion | ScoreQuestion | NoulQuestion,
    Field(discriminator="type"),
]


class SystemOneRequest(BaseModel):
    model: str = "jev-latest"
    state: str
    questions: dict[str, Question]


class ChoiceAnswer(BaseModel):
    type: Literal["choice"] = "choice"
    choice: str
    confidence: float
    probabilities: dict[str, float]


class ScoreAnswer(BaseModel):
    type: Literal["score"] = "score"
    score: float
    confidence: float
    legend: dict[str, str]
    probabilities: dict[str, float]


class NoulAnswer(BaseModel):
    type: Literal["noul"] = "noul"
    noul: float


Answer = ChoiceAnswer | ScoreAnswer | NoulAnswer


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class SystemOneResponse(BaseModel):
    model: str
    answers: dict[str, Any]
    usage: Usage
