"""Voice adapter routes — owned by Luffy. Registered once in ``app/main.py``.

- ``POST /v1/sessions/{id}/voice-binding`` authenticates the session bearer via
  ``IntakeService.get_session``, checks ``expected_revision`` and issues a
  scoped binding (see ``bindings.py``). The Next.js server route calls this.
- ``POST /v1/voice/advance`` (the agent's ``advance_intake`` tool) authenticates
  ``X-Tool-Secret`` (constant time) AND ``X-Voice-Binding``, resolves the session
  from the binding only, then runs ``advance.VoiceAdvancer``: bounded wait for a
  new persisted patient turn, operation key from binding + turn, shared
  ``IntakeService.advance``, voice-safe result only.

This module never executes SQL or implements extraction; it calls the shared
service only. It never logs binding tokens, tool secrets or transcripts.
"""
from __future__ import annotations

import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, Header

from app.auth import bearer_token
from app.config import get_settings
from app.errors import ApiError
from app.intake_service import IntakeService, get_intake_service
from app.models import ApiErrorResponse, VoiceAdvanceResult, VoiceBindingRequest, VoiceBindingResponse
from app.voice.advance import VoiceAdvancer, get_voice_advancer
from app.voice.bindings import BindingConflict, VoiceBindingStore, get_binding_store

router = APIRouter(tags=["voice"])

_ERRORS = {status: {"model": ApiErrorResponse} for status in (401, 404, 409, 503)}


def get_voice_tool_secret() -> str:
    """Shared secret configured both here (VOICE_TOOL_SECRET) and in the agent's tool header."""
    return get_settings().voice_tool_secret


@router.post("/v1/sessions/{session_id}/voice-binding", response_model=VoiceBindingResponse, responses=_ERRORS)
def create_voice_binding(
    session_id: str,
    body: VoiceBindingRequest,
    token: str = Depends(bearer_token),
    service: IntakeService = Depends(get_intake_service),
    store: VoiceBindingStore = Depends(get_binding_store),
) -> VoiceBindingResponse:
    snapshot = service.get_session(session_id, token)  # 401/404 come from the shared service
    input_hash = hashlib.sha256(
        json.dumps({"route": "voice-binding", "session_id": session_id, "body": body.model_dump()}, sort_keys=True).encode()
    ).hexdigest()
    try:
        issued = store.find(session_id, body.request_id, input_hash)  # a retry keeps its original answer
        if issued is None:
            if body.expected_revision != snapshot.revision:
                raise ApiError(409, "REVISION_CONFLICT", "Reload the current session.", request_id=body.request_id)
            issued = store.issue(session_id, body.request_id, input_hash, session_token=token)
    except BindingConflict:
        raise ApiError(409, "IDEMPOTENCY_MISMATCH", "This request ID was already used with different content.",
                       request_id=body.request_id) from None
    return VoiceBindingResponse(binding_token=issued.binding_token, expires_at=issued.expires_at)


@router.post("/v1/voice/advance", response_model=VoiceAdvanceResult, responses=_ERRORS)
def voice_advance(
    x_tool_secret: str | None = Header(default=None),
    x_voice_binding: str | None = Header(default=None),
    expected_secret: str = Depends(get_voice_tool_secret),
    store: VoiceBindingStore = Depends(get_binding_store),
    service: IntakeService = Depends(get_intake_service),
    advancer: VoiceAdvancer = Depends(get_voice_advancer),
) -> VoiceAdvanceResult:
    if not expected_secret:
        raise ApiError(503, "VOICE_TOOL_NOT_CONFIGURED", "Voice tool authentication is not configured.")
    secret_ok = hmac.compare_digest((x_tool_secret or "").encode(), expected_secret.encode())
    binding = store.resolve(x_voice_binding or "")
    if not secret_ok or binding is None:
        # One response for every auth failure: no hint which header was wrong or whether a session exists.
        raise ApiError(401, "VOICE_AUTH_FAILED", "Voice tool authentication failed. Reconnect voice.")
    # Session identity comes only from the binding; the request body is ignored.
    return advancer.advance(service, binding)
