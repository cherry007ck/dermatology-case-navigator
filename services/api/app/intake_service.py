"""Frozen service seam shared by the HTTP routes and the voice adapter.

Method names and DTO arguments below are frozen at S0 (docs/03-api-contract.md).
Owner after S0: Zoro. Luffy's ``app/voice`` imports ``IntakeService`` and
``get_intake_service`` only.

Import paths:
    from app.intake_service import IntakeService, get_intake_service
    from app.models import ...

Routes obtain the service through FastAPI dependency injection:
    service: IntakeService = Depends(get_intake_service)

``advance`` takes no token: callers MUST authenticate first (the session route
checks the bearer token via ``get_session``; the voice route checks its binding).

S1 implementation: ``app.service.EncounterService`` over the repository chosen by
``DATA_BACKEND`` (``memory`` for tests/isolated development, ``exasol`` for live mode).
Exasol mode never falls back to memory: missing configuration is a 503
``STORAGE_NOT_CONFIGURED``. Extraction is still the labelled fixture extractor (S2 replaces it).
``app.stub_service.FixtureStubIntakeService`` remains only for tests that construct it directly.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from app.models import (
    AdvanceRequest,
    AdvanceResult,
    AppendTurnsRequest,
    ClinicianNote,
    ClinicianNoteRequest,
    CollectionsResponse,
    ConfirmRequest,
    CorrectionRequest,
    CreateSessionRequest,
    CreateSessionResponse,
    ReadinessResponse,
    SessionSnapshot,
    SkipQuestionRequest,
)


class IntakeService(Protocol):
    # --- frozen v1 methods -------------------------------------------------
    def create_session(self, request: CreateSessionRequest) -> CreateSessionResponse: ...

    def get_session(self, session_id: str, session_token: str) -> SessionSnapshot: ...

    def append_turns(
        self, session_id: str, session_token: str, request: AppendTurnsRequest
    ) -> SessionSnapshot: ...

    def advance(self, session_id: str, request: AdvanceRequest) -> AdvanceResult: ...

    def skip_question(
        self, session_id: str, session_token: str, request: SkipQuestionRequest
    ) -> SessionSnapshot: ...

    def correct_turn(
        self, session_id: str, session_token: str, request: CorrectionRequest
    ) -> SessionSnapshot: ...

    def confirm(self, session_id: str, session_token: str, request: ConfirmRequest) -> SessionSnapshot: ...

    def add_clinician_note(
        self, session_id: str, session_token: str, request: ClinicianNoteRequest
    ) -> ClinicianNote: ...

    # --- read-only helpers for /v1/readiness and /v1/collections ------------
    def readiness(self) -> ReadinessResponse: ...

    def list_collections(self) -> CollectionsResponse: ...


def build_pipeline(settings):
    """EXTRACTOR_MODE=meta uses Meta Model API candidates; fixture uses the labelled keyword rules.

    Meta mode with a missing key, model or https base URL is reported honestly: readiness is false and
    ``advance`` returns 503 EXTRACTION_UNAVAILABLE. It never silently switches to the keyword rules.
    """
    from app.pipeline import IntakePipeline

    if settings.extractor_mode == "meta":
        from app.extraction.meta import MetaCandidateProvider

        return IntakePipeline(MetaCandidateProvider(settings.model_api_key, settings.model_base_url,
                                                    settings.model_name))
    if settings.extractor_mode == "fixture":
        from app.extraction.rules import RuleCandidateProvider

        return IntakePipeline(RuleCandidateProvider())
    raise ValueError("EXTRACTOR_MODE must be 'fixture' or 'meta'")


@lru_cache
def _build_service() -> IntakeService:
    from app.config import get_settings
    from app.fixtures import get_fixture_bundle
    from app.service import EncounterService

    settings = get_settings()
    bundle = get_fixture_bundle()
    if settings.data_backend == "exasol":
        from app.repositories.exasol import ExasolEncounterRepository

        repository = ExasolEncounterRepository(
            settings.exasol_dsn, settings.exasol_user, settings.exasol_password, settings.exasol_schema
        )
    elif settings.data_backend == "memory":
        from app.repositories.memory import MemoryEncounterRepository

        repository = MemoryEncounterRepository(bundle.collection, bundle.cases)
    else:
        raise ValueError("DATA_BACKEND must be 'memory' or 'exasol'")
    return EncounterService(settings, repository, build_pipeline(settings))


def get_intake_service() -> IntakeService:
    from app.errors import ApiError
    from app.repositories.base import StorageUnavailable

    try:
        return _build_service()
    except (StorageUnavailable, ValueError, RuntimeError):
        # Configuration problem (never a credential value). Do not silently use memory instead.
        raise ApiError(503, "STORAGE_NOT_CONFIGURED", "Encounter storage is not configured on this server.") from None
