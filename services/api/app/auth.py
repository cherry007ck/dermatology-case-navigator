"""Request authentication helpers shared by route modules."""
from __future__ import annotations

import hmac

from fastapi import Header

from app.config import get_settings
from app.errors import ApiError


def bearer_token(authorization: str | None = Header(default=None)) -> str:
    """Extract ``Authorization: Bearer <session_token>``; 401 when missing or malformed."""
    if not authorization:
        raise ApiError(401, "UNAUTHORIZED", "Session token required.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ApiError(401, "UNAUTHORIZED", "Session token required.")
    return token.strip()


def require_demo_access(x_demo_access_code: str | None = Header(default=None)) -> None:
    """Check ``X-Demo-Access-Code``. Fictional-demo gate, not a clinician identity system."""
    expected = get_settings().effective_demo_access_code()
    if expected is None:
        raise ApiError(503, "DEMO_ACCESS_NOT_CONFIGURED", "Demo access is not configured on this server.")
    if not x_demo_access_code or not hmac.compare_digest(x_demo_access_code.encode(), expected.encode()):
        raise ApiError(403, "BAD_DEMO_CODE", "Demo access code is not valid.")
