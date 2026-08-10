"""Protected internal maintenance routes (cleanup cron)."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException, Request

from app.core import config as app_config
from app.services.retention_cleanup import cleanup_expired_fixed_documents
from app.services.vercel_oidc import extract_vercel_oidc_token

router = APIRouter(prefix="/internal", tags=["internal"])


def _require_cleanup_auth(
    *,
    authorization: str | None,
    x_cleanup_secret: str | None,
) -> None:
    """
    Authenticate cleanup invocations.

    Official Vercel Cron (preferred):
      Authorization: Bearer <CRON_SECRET>

    Manual/ops fallback:
      X-Cleanup-Secret: <CLEANUP_JOB_SECRET or CRON_SECRET>
    """
    accepted = app_config.resolve_cleanup_secrets()
    if not accepted:
        raise HTTPException(status_code=503, detail="Cleanup job is not configured.")

    # 1) Official Vercel Cron Authorization header.
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token.strip():
            presented = token.strip()
            if any(hmac.compare_digest(presented, expected) for expected in accepted):
                return

    # 2) Manual header for curl / external schedulers.
    if x_cleanup_secret and x_cleanup_secret.strip():
        presented = x_cleanup_secret.strip()
        if any(hmac.compare_digest(presented, expected) for expected in accepted):
            return

    raise HTTPException(status_code=401, detail="Unauthorized.")


async def _run_cleanup(
    request: Request,
    x_cleanup_secret: str | None,
) -> dict:
    authorization = request.headers.get("authorization")
    _require_cleanup_auth(
        authorization=authorization,
        x_cleanup_secret=x_cleanup_secret,
    )
    report = cleanup_expired_fixed_documents(
        retention_hours=app_config.document_retention_hours(),
        oidc_token=extract_vercel_oidc_token(request),
    )
    return {"ok": True, "cleanup": report.to_dict()}


@router.get("/cleanup-fixed-documents")
async def cleanup_fixed_documents_get(
    request: Request,
    x_cleanup_secret: str | None = Header(default=None, alias="X-Cleanup-Secret"),
):
    """
    Vercel Cron entrypoint (GET).

    Secured by CRON_SECRET via Authorization: Bearer <secret>.
    Schedule is declared in vercel.json.
    """
    return await _run_cleanup(request, x_cleanup_secret)


@router.post("/cleanup-fixed-documents")
async def cleanup_fixed_documents_post(
    request: Request,
    x_cleanup_secret: str | None = Header(default=None, alias="X-Cleanup-Secret"),
):
    """Manual / alternate scheduler entrypoint (POST). Same auth rules as GET."""
    return await _run_cleanup(request, x_cleanup_secret)
