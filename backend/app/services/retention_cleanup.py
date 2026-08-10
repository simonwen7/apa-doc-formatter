"""Fixed-document retention cleanup (Phase 3C).

Deletes only objects under the approved `fixed/` namespace that exceed
DOCUMENT_RETENTION_HOURS. Idempotent and safe against malformed pathnames.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from app.core import config as app_config
from app.services.document_store import (
    StoredFixedObject,
    delete_fixed_document,
    list_fixed_objects,
)

logger = logging.getLogger(__name__)


@dataclass
class CleanupReport:
    retention_hours: int
    scanned: int = 0
    expired: int = 0
    deleted: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "retention_hours": self.retention_hours,
            "scanned": self.scanned,
            "expired": self.expired,
            "deleted": self.deleted,
            "skipped": self.skipped,
            "error_count": len(self.errors),
        }


def _is_expired(obj: StoredFixedObject, *, now: float, retention_hours: int) -> bool:
    age_seconds = now - float(obj.created_at)
    return age_seconds >= retention_hours * 3600


def cleanup_expired_fixed_documents(
    *,
    retention_hours: int | None = None,
    now: float | None = None,
    objects: list[StoredFixedObject] | None = None,
    oidc_token: str | None = None,
) -> CleanupReport:
    """
    Delete expired owner-scoped fixed documents.

    Safe to run repeatedly. Failures on one item do not abort the batch.
    Never deletes outside the fixed/ namespace (list_fixed_objects enforces this).
    """
    hours = (
        app_config.document_retention_hours()
        if retention_hours is None
        else int(retention_hours)
    )
    if hours <= 0:
        raise ValueError("retention_hours must be positive")

    current = time.time() if now is None else float(now)
    report = CleanupReport(retention_hours=hours)

    try:
        candidates = (
            list_fixed_objects(oidc_token=oidc_token)
            if objects is None
            else objects
        )
    except Exception as exc:
        logger.exception("cleanup_list_failed")
        report.errors.append(f"list_failed:{type(exc).__name__}")
        return report

    report.scanned = len(candidates)

    for obj in candidates:
        # Defense: only touch fixed/{uuid}/{uuid}.docx paths.
        if not obj.pathname.startswith("fixed/"):
            report.skipped += 1
            continue
        if not _is_expired(obj, now=current, retention_hours=hours):
            report.skipped += 1
            continue

        report.expired += 1
        try:
            ok = delete_fixed_document(
                obj.user_id,
                obj.document_id,
                oidc_token=oidc_token,
            )
            if ok:
                report.deleted += 1
            else:
                report.errors.append(f"delete_failed:{obj.document_id}")
        except Exception as exc:
            report.errors.append(f"delete_error:{type(exc).__name__}")
            logger.info(
                "cleanup_item_failed document_id=%s error=%s",
                obj.document_id,
                type(exc).__name__,
            )

    logger.info(
        "cleanup_complete scanned=%s expired=%s deleted=%s skipped=%s errors=%s",
        report.scanned,
        report.expired,
        report.deleted,
        report.skipped,
        len(report.errors),
    )
    return report


def assert_local_cleanup_stays_in_fixed_dir(path: str) -> bool:
    """Helper for tests: path must resolve under FIXED_DIR."""
    from pathlib import Path

    target = Path(path).resolve()
    root = app_config.FIXED_DIR.resolve()
    try:
        target.relative_to(root)
        return True
    except ValueError:
        return False
