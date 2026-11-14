"""Shared DTOs for the v1 contract.

Owner after S0: Zoro. Luffy's voice module imports these and never redefines them.

Domain objects mirror ``contracts/domain.schema.json`` field-for-field (names,
required sets, enums, nullability). ``tests/test_contract_alignment.py`` fails
if they drift. Endpoint request/response models follow ``docs/03-api-contract.md``.
Every model forbids unknown fields, matching ``additionalProperties: false``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Domain objects (contracts/domain.schema.json $defs)
# ---------------------------------------------------------------------------

SourceType = Literal["patient_turn", "case_passage"]
SourceKind = Literal["published", "synthetic"]
SessionState = Literal["intake", "awaiting_answer", "ready_to_confirm", "confirmed"]
AdvanceAction = Literal["ask", "ready_to_confirm", "waiting_for_transcript"]
NoMatchReason = Literal["insufficient_information", "conflicting_details", "no_comparable_cases"]


class EvidenceRef(ContractModel):
    source_type: SourceType
    source_id: str
    quote: str = Field(min_length=1)


class SourceReview(ContractModel):
    status: Literal["pending", "reviewed", "fixture_checked"]
    reviewer: str | None
    reviewed_at: datetime | None


class Passage(ContractModel):
    passage_id: str
    case_id: str
    text: str = Field(min_length=1)
    section: str
    locator: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class CaseFeature(ContractModel):
    key: str
    value: str
    polarity: Literal["affirmed", "negated"]
    evidence: list[EvidenceRef]


class SupportedStatement(ContractModel):
    text: str
    evidence: list[EvidenceRef]


class ArticleCitation(ContractModel):
    """Bibliographic and licence metadata of a published case, captured from the source article's
    own metadata (PMC JATS XML). Synthetic cases have none."""
    authors: list[str]
    journal: str
    year: str
    license_name: str
    license_url: str


class CaseAttribution(ContractModel):
    """Attribution shown on a published case card. ``null`` on synthetic cards."""
    authors: list[str]
    journal: str
    year: str
    doi: str | None
    pmid: str | None
    pmcid: str
    license_name: str
    license_url: str
    source_review_status: Literal["reviewed"]
    clinical_reviewed: bool


class CaseRecord(ContractModel):
    case_id: str
    collection_id: str
    source_kind: SourceKind
    title: str
    article_url: str | None
    article_identifiers: dict[str, str]
    source_version: str
    license: str
    source_review: SourceReview
    clinical_reviewed: bool
    passages: list[Passage]
    features: list[CaseFeature]
    actions: list[SupportedStatement]
    outcomes: list[SupportedStatement]
    # Optional so records stored before this field (and all synthetic records) stay valid and
    # serialize unchanged; required for published records by app.published.
    citation: ArticleCitation | None = Field(default=None, exclude_if=lambda v: v is None)


class Collection(ContractModel):
    collection_id: str
    mode: SourceKind
    version: str
    case_count: int = Field(ge=0)
    source_review_count: int = Field(ge=0)
    clinical_reviewed: bool


class PatientFact(ContractModel):
    fact_id: str
    key: str
    value: str | None
    status: Literal["reported", "negated", "unknown", "conflicting"]
    evidence: list[EvidenceRef]


class TurnInput(ContractModel):
    turn_id: str
    role: Literal["patient", "agent"]
    origin: Literal["typed", "voice_transcript"]
    text: str = Field(min_length=1)
    reply_to_question_id: str | None


class Turn(ContractModel):
    turn_id: str
    role: Literal["patient", "agent"]
    origin: Literal["typed", "voice_transcript", "correction"]
    text: str = Field(min_length=1)
    reply_to_question_id: str | None
    supersedes_turn_id: str | None
    sequence: int = Field(ge=0)
    created_at: datetime


class ComparisonBasis(ContractModel):
    case_ids: list[str]
    contrasting_feature: str
    evidence: list[EvidenceRef]


class Question(ContractModel):
    question_id: str
    kind: Literal["intake_gap", "case_difference"]
    template_id: str
    text: str
    status: Literal["asked", "answered", "unknown", "skipped"]
    evidence: list[EvidenceRef]
    reason: str
    comparison_basis: ComparisonBasis | None
    answer_turn_ids: list[str]


class CaseCard(ContractModel):
    case_id: str
    source_kind: SourceKind
    title: str
    article_url: str | None
    shared_features: list[SupportedStatement]
    important_differences: list[SupportedStatement]
    actions: list[SupportedStatement]
    outcomes: list[SupportedStatement]
    passages: list[Passage]
    # Always serialized (null for synthetic). The default only keeps search snapshots stored
    # before this field readable.
    attribution: CaseAttribution | None = None


class CaseChange(ContractModel):
    case_id: str
    change: Literal["appeared", "removed", "moved", "unchanged"]
    from_rank: Annotated[int, Field(ge=1)] | None
    to_rank: Annotated[int, Field(ge=1)] | None
    reason: str
    evidence: list[EvidenceRef]


class ExcludedCase(ContractModel):
    case_id: str
    reason: Literal[
        "site_conflict",
        "exposure_conflict",
        "no_shared_symptom",
        "no_shared_site",
        "unreviewed_source",
        "source_mode_mismatch",
        "invalid_evidence",
    ]
    evidence: list[EvidenceRef]


class ScoreComponents(ContractModel):
    case_id: str
    shared_site: int = Field(ge=0)
    shared_symptom: int = Field(ge=0)
    shared_duration: int = Field(ge=0)
    shared_exposure: int = Field(ge=0)
    total: int = Field(ge=0)


class SearchVersion(ContractModel):
    search_id: str
    patient_revision: int = Field(ge=0)
    algorithm_version: str
    collection_version: str
    input_fact_ids: list[str]
    ranked_case_ids: list[str]
    cards: list[CaseCard]
    excluded_cases: list[ExcludedCase]
    score_components: list[ScoreComponents]
    changes: list[CaseChange]
    no_match_reason: NoMatchReason | None
    created_at: datetime


class BriefItem(ContractModel):
    text: str
    status: Literal["reported", "missing", "conflicting"]
    evidence: list[EvidenceRef]


class DoctorClarification(ContractModel):
    text: str
    basis_fact_ids: list[str]
    basis_case_ids: list[str]


class Brief(ContractModel):
    patient_revision: int = Field(ge=0)
    summary_items: list[BriefItem]
    timeline_items: list[BriefItem]
    prior_treatment_items: list[BriefItem]
    unresolved_items: list[BriefItem]
    doctor_clarifications: list[DoctorClarification]


class ClinicianNote(ContractModel):
    note_id: str
    patient_revision: int = Field(ge=0)
    note_text: str
    author_label: str
    created_at: datetime


class Modes(ContractModel):
    storage: Literal["memory", "exasol"]
    extractor: Literal["fixture", "meta"]


class SessionSnapshot(ContractModel):
    session_id: str
    revision: int = Field(ge=0)
    state: SessionState
    confirmed_revision: Annotated[int, Field(ge=0)] | None
    turns: list[Turn]
    facts: list[PatientFact]
    questions: list[Question]
    search_history: list[SearchVersion]
    brief: Brief | None
    clinician_notes: list[ClinicianNote]
    warnings: list[str]
    modes: Modes
    collection: Collection


class AdvanceResult(ContractModel):
    snapshot: SessionSnapshot
    action: AdvanceAction
    question: Question | None


class VoiceAdvanceResult(ContractModel):
    action: AdvanceAction
    question_id: str | None
    question_text: str | None
    spoken_message: str


# ---------------------------------------------------------------------------
# Endpoint DTOs (docs/03-api-contract.md "Routes")
# ---------------------------------------------------------------------------


class HealthResponse(ContractModel):
    status: Literal["ok"]


class ReadinessResponse(ContractModel):
    storage: Literal["memory", "exasol"]
    extractor: Literal["fixture", "meta"]
    collection_mode: SourceKind
    loaded_cases: int = Field(ge=0)
    ready: bool


class CollectionsResponse(ContractModel):
    collections: list[Collection]


class CreateSessionRequest(ContractModel):
    request_id: str
    collection_id: str


class CreateSessionResponse(ContractModel):
    session_id: str
    session_token: str
    snapshot: SessionSnapshot


class AppendTurnsRequest(ContractModel):
    request_id: str
    expected_revision: int = Field(ge=0)
    turns: list[TurnInput] = Field(min_length=1)


class AdvanceRequest(ContractModel):
    request_id: str
    expected_revision: int = Field(ge=0)


class SkipQuestionRequest(ContractModel):
    request_id: str
    expected_revision: int = Field(ge=0)
    question_id: str


class ConfirmRequest(ContractModel):
    request_id: str
    expected_revision: int = Field(ge=0)


class CorrectionRequest(ContractModel):
    request_id: str
    expected_revision: int = Field(ge=0)
    replaces_turn_id: str
    replacement_text: str = Field(min_length=1)


class ClinicianNoteRequest(ContractModel):
    request_id: str
    expected_revision: int = Field(ge=0)
    note_text: str = Field(min_length=1)
    author_label: str = Field(min_length=1)


class VoiceBindingRequest(ContractModel):
    request_id: str
    expected_revision: int = Field(ge=0)


class VoiceBindingResponse(ContractModel):
    binding_token: str
    expires_at: datetime


class ApiErrorBody(ContractModel):
    code: str
    message: str
    retryable: bool


class ApiErrorResponse(ContractModel):
    error: ApiErrorBody
    request_id: str | None
