"""Extract Vercel infrastructure OIDC from the current Function request.

This is NOT user authentication. Supabase Bearer remains the user principal.
"""

from __future__ import annotations

from fastapi import Request

_VERCEL_OIDC_HEADER = "x-vercel-oidc-token"


def extract_vercel_oidc_token(request: Request) -> str | None:
    """
    Read the platform OIDC token from the trusted Vercel Function request.

    Only `x-vercel-oidc-token` is accepted. The Supabase `Authorization`
    header is intentionally ignored here.
    """
    value = request.headers.get(_VERCEL_OIDC_HEADER)
    if not value:
        return None
    token = value.strip()
    return token or None
