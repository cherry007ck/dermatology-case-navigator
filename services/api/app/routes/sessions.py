"""Session routes. Every route delegates to the frozen ``IntakeService`` seam."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import bearer_token, require_demo_access
from app.intake_service import IntakeService, get_intake_service
from app.models import (
    AdvanceRequest,
    AdvanceResult,
    ApiErrorResponse,
    AppendTurnsRequest,
    ClinicianNote,
    ClinicianNoteRequest,
    ConfirmRequest,
    CorrectionRequest,
    CreateSessionRequest,
    CreateSessionResponse,
    SessionSnapshot,
    SkipQuestionRequest,
)

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])

_ERRORS = {
    status: {"model": ApiErrorResponse} for status in (401, 403, 404, 409, 422, 429, 503)
}


@router.post("", response_model=CreateSessionResponse, dependencies=[Depends(require_demo_access)],
             responses=_ERRORS)
def create_session(
    body: CreateSessionRequest, service: IntakeService = Depends(get_intake_service)
) -> CreateSessionResponse:
    return service.create_session(body)


@router.get("/{session_id}", response_model=SessionSnapshot, responses=_ERRORS)
def get_session(
    session_id: str,
    token: str = Depends(bearer_token),
    service: IntakeService = Depends(get_intake_service),
) -> SessionSnapshot:
    return service.get_session(session_id, token)


@router.post("/{session_id}/turns", response_model=SessionSnapshot, responses=_ERRORS)
def append_turns(
    session_id: str,
    body: AppendTurnsRequest,
    token: str = Depends(bearer_token),
    service: IntakeService = Depends(get_intake_service),
) -> SessionSnapshot:
    return service.append_turns(session_id, token, body)


@router.post("/{session_id}/advance", response_model=AdvanceResult, responses=_ERRORS)
def advance(
    session_id: str,
    body: AdvanceRequest,
    token: str = Depends(bearer_token),
    service: IntakeService = Depends(get_intake_service),
) -> AdvanceResult:
    service.get_session(session_id, token)  # authenticate before the token-less advance call
    return service.advance(session_id, body)


@router.post("/{session_id}/skip", response_model=SessionSnapshot, responses=_ERRORS)
def skip_question(
    session_id: str,
    body: SkipQuestionRequest,
    token: str = Depends(bearer_token),
    service: IntakeService = Depends(get_intake_service),
) -> SessionSnapshot:
    return service.skip_question(session_id, token, body)


@router.post("/{session_id}/confirm", response_model=SessionSnapshot, responses=_ERRORS)
def confirm(
    session_id: str,
    body: ConfirmRequest,
    token: str = Depends(bearer_token),
    service: IntakeService = Depends(get_intake_service),
) -> SessionSnapshot:
    return service.confirm(session_id, token, body)


@router.post("/{session_id}/corrections", response_model=SessionSnapshot, responses=_ERRORS)
def correct_turn(
    session_id: str,
    body: CorrectionRequest,
    token: str = Depends(bearer_token),
    service: IntakeService = Depends(get_intake_service),
) -> SessionSnapshot:
    return service.correct_turn(session_id, token, body)


@router.post("/{session_id}/clinician-notes", response_model=ClinicianNote, responses=_ERRORS)
def add_clinician_note(
    session_id: str,
    body: ClinicianNoteRequest,
    token: str = Depends(bearer_token),
    service: IntakeService = Depends(get_intake_service),
) -> ClinicianNote:
    return service.add_clinician_note(session_id, token, body)
