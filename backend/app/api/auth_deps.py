"""Supabase access-token verification (Phase 3C).

Official mechanism (supabase-py / supabase-auth):
  client.auth.get_claims(jwt=<access_token>)

Per Supabase docs, get_claims verifies the JWT against the project's JWKS
endpoint (/.well-known/jwks.json), often from cache. Prefer this over
get_user(), which always hits the Auth server for each token.

For legacy HS256 shared-secret projects, the SDK may fall back to a network
user check. Invalid/expired tokens raise / return None → mapped to HTTP 401.

Verification is injectable for unit tests (no live Supabase required).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Callable, Optional, Protocol

from fastapi import HTTPException

from app.core.config import SUPABASE_ANON_KEY, SUPABASE_URL

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AuthenticatedUser:
    """Safe authenticated principal. Never includes the raw access token."""

    user_id: str


class TokenVerifier(Protocol):
    def __call__(self, access_token: str) -> AuthenticatedUser: ...


_override_verifier: Optional[TokenVerifier] = None


def set_token_verifier(verifier: Optional[TokenVerifier]) -> None:
    """Test hook: replace production Supabase verification."""
    global _override_verifier
    _override_verifier = verifier


def reset_token_verifier() -> None:
    set_token_verifier(None)


def _extract_user_id(claims_obj) -> str:
    claims = getattr(claims_obj, "claims", None)
    if claims is None and isinstance(claims_obj, dict):
        claims = claims_obj.get("claims") or claims_obj

    user_id = None
    if isinstance(claims, dict):
        user_id = claims.get("sub")
    else:
        user_id = getattr(claims, "sub", None)

    if not user_id or not _UUID_RE.fullmatch(str(user_id)):
        raise HTTPException(status_code=401, detail="Authentication required.")
    return str(user_id)


def verify_supabase_access_token(access_token: str) -> AuthenticatedUser:
    """Verify a Supabase access token and return the authenticated user."""
    if _override_verifier is not None:
        return _override_verifier(access_token)

    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        logger.error("Supabase server auth is not configured.")
        raise HTTPException(
            status_code=503,
            detail="Authentication service is not configured.",
        )

    if not access_token or not access_token.strip():
        raise HTTPException(status_code=401, detail="Authentication required.")

    try:
        from supabase import create_client

        client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        response = client.auth.get_claims(jwt=access_token.strip())
    except HTTPException:
        raise
    except Exception:
        # Do not leak verification internals.
        logger.info("supabase_token_verification_failed")
        raise HTTPException(status_code=401, detail="Authentication required.") from None

    if response is None:
        raise HTTPException(status_code=401, detail="Authentication required.")

    try:
        user_id = _extract_user_id(response)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication required.") from None

    return AuthenticatedUser(user_id=user_id)
