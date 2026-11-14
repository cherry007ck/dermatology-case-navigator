"""Candidate facts proposed by an extraction provider. Untrusted until server validation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from app.models import Question, Turn


class Candidate(BaseModel):
    """One proposed fact. ``quote`` must be an exact substring of the cited patient turn."""

    model_config = ConfigDict(extra="ignore")

    key: str
    value: str | None = None
    status: Literal["reported", "negated", "unknown"] = "reported"
    turn_id: str
    quote: str


@dataclass(frozen=True)
class ExtractionInput:
    """Active patient turns only. ``targets`` are the turns to extract from now; the rest is context.
    ``questions`` maps a turn ID to the question that turn answers (for short answers)."""

    patient_turns: list[Turn]
    targets: list[Turn]
    questions: dict[str, Question] = field(default_factory=dict)


class ExtractionUnavailable(RuntimeError):
    """Provider failed, timed out or returned unusable data. Carries no provider text."""


class CandidateProvider(Protocol):
    mode: Literal["fixture", "meta"]

    def extract(self, data: ExtractionInput) -> list[Candidate]: ...
