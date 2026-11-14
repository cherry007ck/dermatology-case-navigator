"""Scoped voice bindings — Luffy's voice module.

A binding lets the ElevenLabs webhook act for exactly one session without the
model ever seeing the session bearer token. Properties (docs/03-api-contract.md):

- random and unguessable: HMAC-SHA256(process key, binding salt); the salt is random
- scoped to one session; resolved server-side, never taken from the model
- expires after 30 minutes; revocable; a new binding revokes the previous one
- the binding token is stored only as a SHA-256 hash; compared in constant time
- idempotent: the same (session, request_id, content) returns the same binding

To call the frozen ``IntakeService.get_session(session_id, session_token)`` from the
webhook, a binding keeps the session bearer that was presented when it was issued.
That bearer lives only in this process's memory: never persisted, logged, returned
or sent to ElevenLabs. It is dropped when the binding is revoked or replaced, and
an expired binding never yields it.

Bindings are in-memory for the single-process prototype. A restart invalidates
them; the browser treats the resulting 401 as "reconnect voice", not data loss.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import lru_cache

BINDING_TTL = timedelta(minutes=30)


def binding_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class _Binding:
    session_id: str
    token_hash: str
    expires_at: datetime
    session_token: str | None = field(default=None, repr=False)
    revoked: bool = False


@dataclass(frozen=True)
class IssuedBinding:
    binding_token: str
    expires_at: datetime


@dataclass(frozen=True)
class ResolvedBinding:
    session_id: str
    binding_hash: str
    session_token: str = field(repr=False)


class BindingConflict(Exception):
    """Request ID reused with different content."""


class VoiceBindingStore:
    def __init__(self, *, now=lambda: datetime.now(UTC)) -> None:
        self._key = secrets.token_bytes(32)
        self._now = now
        self._by_hash: dict[str, _Binding] = {}
        self._active: dict[str, str] = {}  # session_id -> token_hash
        self._issued: dict[tuple[str, str], tuple[str, str, datetime]] = {}  # (session, request_id) -> (input_hash, salt, expiry)
        self._lock = threading.Lock()

    def _token(self, session_id: str, salt: str) -> str:
        message = f"dcn.voice-binding.v1|{session_id}|{salt}".encode()
        return "vb_" + hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def find(self, session_id: str, request_id: str, input_hash: str) -> IssuedBinding | None:
        """Original response for a retried request; BindingConflict if the content differs."""
        with self._lock:
            previous = self._issued.get((session_id, request_id))
            if previous is None:
                return None
            stored_hash, salt, expires_at = previous
            if stored_hash != input_hash:
                raise BindingConflict
            return IssuedBinding(self._token(session_id, salt), expires_at)

    def issue(self, session_id: str, request_id: str, input_hash: str, session_token: str) -> IssuedBinding:
        if (existing := self.find(session_id, request_id, input_hash)) is not None:
            return existing
        with self._lock:
            if old := self._active.get(session_id):
                self._revoke(old)
            salt = secrets.token_hex(16)
            token = self._token(session_id, salt)
            expires_at = (self._now() + BINDING_TTL).replace(microsecond=0)
            token_hash = binding_hash(token)
            self._by_hash[token_hash] = _Binding(session_id, token_hash, expires_at, session_token)
            self._active[session_id] = token_hash
            self._issued[(session_id, request_id)] = (input_hash, salt, expires_at)
            return IssuedBinding(token, expires_at)

    def _revoke(self, token_hash: str) -> None:
        binding = self._by_hash[token_hash]
        binding.revoked = True
        binding.session_token = None

    def resolve(self, token: str) -> ResolvedBinding | None:
        """Live binding for a presented token, else None (unknown, revoked or expired)."""
        presented = binding_hash(token or "")
        with self._lock:
            match = None
            for token_hash, binding in self._by_hash.items():
                if hmac.compare_digest(presented, token_hash):
                    match = binding
            if match is None or match.revoked or match.session_token is None:
                return None
            if self._now() >= match.expires_at:
                match.session_token = None
                return None
            return ResolvedBinding(match.session_id, match.token_hash, match.session_token)

    def revoke_session(self, session_id: str) -> None:
        with self._lock:
            if token_hash := self._active.pop(session_id, None):
                self._revoke(token_hash)


@lru_cache
def get_binding_store() -> VoiceBindingStore:
    return VoiceBindingStore()
