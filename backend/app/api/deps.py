"""FastAPI dependencies for authenticated document routes."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from app.api.auth_deps import AuthenticatedUser, verify_supabase_access_token


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Authentication required.")
    return token.strip()


def get_current_user(
    authorization: str | None = Header(default=None),
) -> AuthenticatedUser:
    """
    Require a verified Supabase access token.

    Identity is derived only from verified claims — never from request body.
    """
    token = _bearer_token(authorization)
    return verify_supabase_access_token(token)


# Alias used by routes for clarity.
require_authenticated_user = get_current_user
