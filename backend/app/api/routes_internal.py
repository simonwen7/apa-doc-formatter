"""Protected internal maintenance routes (cleanup cron)."""

from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, HTTPException

from app.core import config as app_config
from app.services.retention_cleanup import cleanup_expired_fixed_documents

router = APIRouter(prefix="/internal", tags=["internal"])


def _require_cleanup_secret(secret: str | None) -> None:
    expected = (app_config.CLEANUP_JOB_SECRET or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Cleanup job is not configured.")

    if not secret or not hmac.compare_digest(expected, secret.strip()):
        raise HTTPException(status_code=401, detail="Unauthorized.")


@router.post("/cleanup-fixed-documents")
async def cleanup_fixed_documents(
    x_cleanup_secret: str | None = Header(default=None, alias="X-Cleanup-Secret"),
):
    """
    Delete expired fixed documents under the `fixed/` namespace.

    Protect with CLEANUP_JOB_SECRET. Configure a Vercel Cron (or equivalent)
    to call this endpoint periodically — not enabled automatically by this phase.
    """
    _require_cleanup_secret(x_cleanup_secret)
    report = cleanup_expired_fixed_documents()
    return {"ok": True, "cleanup": report.to_dict()}
