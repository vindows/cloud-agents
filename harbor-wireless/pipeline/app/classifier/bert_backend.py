"""Lightweight ML backend behind the Jev-compatible System One shim.

Uses TF-IDF + logistic regression for category/choice signals (BERT-class
intent model stand-in that stays demo-friendly without a GPU). Keyword
overlap backs score and noul questions so the same /v1/systemone contract
works for triage steps.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from app.classifier.base import ClassifierBackend
from app.models.jev import (
    ChoiceAnswer,
    ChoiceQuestion,
    NoulAnswer,
    NoulQuestion,
    Question,
    ScoreAnswer,
    ScoreQuestion,
    SystemOneRequest,
    SystemOneResponse,
    Usage,
)

CATEGORIES = ("access", "hardware", "network", "applications")

# Seed phrases for the demo classifier — mirrors Harbor Wireless ticket language.
_TRAIN: list[tuple[str, str]] = [
    ("cannot login password reset MFA lockout account disabled SSO AD", "access"),
    ("forgot password unlock my account VPN credentials expired", "access"),
    ("need access to sharepoint mailbox distribution list permission", "access"),
    ("badge not working door access provisioning new hire", "access"),
    ("laptop broken screen cracked keyboard not working docking station", "hardware"),
    ("monitor blank printer offline headset mic mute docking port", "hardware"),
    ("request new laptop phone tablet replacement hardware asset", "hardware"),
    ("mouse clicks stuck webcam no image USB port dead", "hardware"),
    ("wifi down cannot connect VPN tunnel drops packet loss", "network"),
    ("slow internet DNS failure firewall block site unreachable", "network"),
    ("switch port flapping WAN outage latency spike traceroute", "network"),
    ("teams call quality bad network congestion proxy issue", "network"),
    ("outlook crash excel freeze teams app install license missing", "applications"),
    ("salesforce error SAP timeout Workday login application bug", "applications"),
    ("chrome extension broken software install request adobe license", "applications"),
    ("sharepoint site not loading powerbi report fail app crash", "applications"),
]

_URGENCY_KEYWORDS = {
    0: ("whenever", "low priority", "nice to have", "when possible", "no rush"),
    1: ("this week", "soon", "blocking some", "degraded"),
    2: (
        "urgent",
        "asap",
        "outage",
        "down",
        "cannot work",
        "critical",
        "production",
        "all users",
        "security",
        "breach",
    ),
}


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _confidence_from_probs(probs: Iterable[float]) -> float:
    arr = np.asarray(list(probs), dtype=float)
    if arr.size == 0:
        return 0.0
    # Peakiness vs uniform: 0 flat, 1 peaked
    peak = float(arr.max())
    uniform = 1.0 / arr.size
    return float(max(0.0, min(1.0, (peak - uniform) / (1.0 - uniform + 1e-9))))


def _overlap_score(state: str, phrase: str) -> float:
    a = _tokenize(state)
    b = _tokenize(phrase)
    if not b:
        return 0.0
    return len(a & b) / len(b)


class BertClassifierBackend(ClassifierBackend):
    """Demo BERT-style intent backend (sklearn TF-IDF + logistic)."""

    name = "bert"

    def __init__(self) -> None:
        texts, labels = zip(*_TRAIN, strict=True)
        self._category_pipe: Pipeline = Pipeline(
            [
                (
                    "tfidf",
                    TfidfVectorizer(
                        ngram_range=(1, 2),
                        min_df=1,
                        sublinear_tf=True,
                    ),
                ),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=500,
                        solver="lbfgs",
                    ),
                ),
            ]
        )
        self._category_pipe.fit(list(texts), list(labels))
        self._category_labels = list(self._category_pipe.classes_)

    def predict_category(self, text: str) -> ChoiceAnswer:
        proba = self._category_pipe.predict_proba([text])[0]
        probs = {
            label: float(p)
            for label, p in zip(self._category_labels, proba, strict=True)
        }
        choice = max(probs, key=probs.get)
        return ChoiceAnswer(
            type="choice",
            choice=choice,
            confidence=_confidence_from_probs(probs.values()),
            probabilities=probs,
        )

    def _answer_choice(self, state: str, q: ChoiceQuestion) -> ChoiceAnswer:
        keys = list(q.criteria.keys())
        # Prefer trained category model when criteria match Harbor categories.
        if set(keys) <= set(CATEGORIES) and set(CATEGORIES) <= set(keys):
            raw = self.predict_category(state)
            probs = {k: raw.probabilities.get(k, 0.0) for k in keys}
            total = sum(probs.values()) or 1.0
            probs = {k: v / total for k, v in probs.items()}
            choice = max(probs, key=probs.get)
            return ChoiceAnswer(
                type="choice",
                choice=choice,
                confidence=_confidence_from_probs(probs.values()),
                probabilities=probs,
            )

        # Generic: score each criterion description against state via overlap + TF-IDF cosine
        scores: dict[str, float] = {}
        for key, desc in q.criteria.items():
            blob = f"{key} {desc}"
            overlap = _overlap_score(state, blob)
            # Soft boost if key itself appears
            if key.lower() in state.lower():
                overlap = min(1.0, overlap + 0.35)
            # Instruction keywords also matter
            overlap = max(overlap, 0.5 * _overlap_score(state, q.instructions))
            scores[key] = max(overlap, 1e-6)

        # Softmax
        keys = list(scores.keys())
        logits = np.array([scores[k] for k in keys], dtype=float) * 4.0
        exps = np.exp(logits - logits.max())
        probs_arr = exps / exps.sum()
        probs = {k: float(p) for k, p in zip(keys, probs_arr, strict=True)}
        choice = max(probs, key=probs.get)
        return ChoiceAnswer(
            type="choice",
            choice=choice,
            confidence=_confidence_from_probs(probs.values()),
            probabilities=probs,
        )

    def _answer_score(self, state: str, q: ScoreQuestion) -> ScoreAnswer:
        n = len(q.criteria)
        if n == 0:
            return ScoreAnswer(
                type="score",
                score=0.0,
                confidence=0.0,
                legend={},
                probabilities={},
            )

        level_scores = []
        for i, label in enumerate(q.criteria):
            base = _overlap_score(state, label)
            # Urgency heuristics when rubric looks like urgency
            for tier, kws in _URGENCY_KEYWORDS.items():
                if any(kw in state.lower() for kw in kws):
                    # Prefer matching tier index when rubric length matches 3
                    if n == 3 and i == min(tier, n - 1):
                        base = max(base, 0.55 + 0.15 * tier)
                    elif n != 3 and i == min(tier, n - 1):
                        base = max(base, 0.4)
            # Higher index slightly preferred if outage language present
            if i == n - 1 and any(
                w in state.lower() for w in ("outage", "down", "critical", "asap")
            ):
                base = max(base, 0.75)
            if i == 0 and any(
                w in state.lower() for w in ("whenever", "low priority", "no rush")
            ):
                base = max(base, 0.7)
            level_scores.append(max(base, 0.05))

        logits = np.array(level_scores, dtype=float) * 5.0
        exps = np.exp(logits - logits.max())
        probs_arr = exps / exps.sum()
        probs = {str(i): float(p) for i, p in enumerate(probs_arr)}
        expected = float(sum(i * probs_arr[i] for i in range(n)))
        legend = {str(i): label for i, label in enumerate(q.criteria)}
        return ScoreAnswer(
            type="score",
            score=expected,
            confidence=_confidence_from_probs(probs_arr),
            legend=legend,
            probabilities=probs,
        )

    def _answer_noul(self, state: str, q: NoulQuestion) -> NoulAnswer:
        instr = q.instructions.lower()
        state_l = state.lower()
        true_desc = ""
        false_desc = ""
        if q.criteria:
            true_desc = str(q.criteria.get("true", "")).lower()
            false_desc = str(q.criteria.get("false", "")).lower()

        # Duplicate / similar heuristics
        if "duplicate" in instr or "same issue" in instr or "already open" in instr:
            # Look for ticket-number-like refs or "same as" language
            hit = any(
                phrase in state_l
                for phrase in (
                    "same as",
                    "duplicate",
                    "already reported",
                    "still happening",
                    "again",
                    "as before",
                )
            )
            p = 0.82 if hit else 0.22
            return NoulAnswer(type="noul", noul=p)

        pos = _overlap_score(state, instr + " " + true_desc)
        neg = _overlap_score(state, false_desc) if false_desc else 0.0
        # Instruction tokens that appear in state increase yes probability
        raw = pos - 0.5 * neg
        # Map to (0,1)
        p = 1.0 / (1.0 + math.exp(-6.0 * (raw - 0.25)))
        # Soft prior near 0.45 when little evidence
        if pos < 0.05 and neg < 0.05:
            p = 0.45
        return NoulAnswer(type="noul", noul=float(max(0.01, min(0.99, p))))

    def _answer_one(self, state: str, question: Question):
        if isinstance(question, ChoiceQuestion):
            return self._answer_choice(state, question)
        if isinstance(question, ScoreQuestion):
            return self._answer_score(state, question)
        if isinstance(question, NoulQuestion):
            return self._answer_noul(state, question)
        raise TypeError(f"Unsupported question type: {type(question)}")

    async def systemone(self, request: SystemOneRequest) -> SystemOneResponse:
        answers = {
            name: self._answer_one(request.state, q).model_dump()
            for name, q in request.questions.items()
        }
        # Approximate token usage for demo transparency
        in_tok = max(1, len(request.state.split()) + 20 * len(request.questions))
        out_tok = 8 * len(request.questions)
        return SystemOneResponse(
            model=f"bert-tfidf-local/{request.model}",
            answers=answers,
            usage=Usage(input_tokens=in_tok, output_tokens=out_tok),
        )
