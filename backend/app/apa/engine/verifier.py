from __future__ import annotations

from app.apa.engine.analyzer import analyze_document_path
from app.apa.models import VerificationResult
from app.apa.profile import PROFILE_ID
from app.apa.registry import production_safe_rules


def verify_fix_result(
    output_path: str,
    template_id: str = PROFILE_ID,
    safe_issues_before: int = 0,
    fixes_applied: int = 0,
    author_action_issues: int = 0,
    text_integrity_ok: bool = True,
    document_preservation_ok: bool = True,
    preservation_warnings: list[str] | None = None,
) -> VerificationResult:
    analysis = analyze_document_path(output_path, template_id=template_id)

    production_ids = {rule.rule_id for rule in production_safe_rules(template_id)}
    remaining = [
        issue
        for issue in analysis.safe_auto_fix
        if issue.rule_id in production_ids
    ]
    remaining_ids = sorted({issue.rule_id for issue in remaining})

    verified = (
        len(remaining) == 0
        and text_integrity_ok
        and document_preservation_ok
    )
    failure_reason = None
    if not verified:
        reasons = []
        if remaining:
            reasons.append(f"Remaining SAFE_AUTO_FIX issues: {', '.join(remaining_ids)}")
        if not text_integrity_ok:
            reasons.append("text integrity failed")
        if not document_preservation_ok:
            reasons.append("document preservation failed")
        failure_reason = "; ".join(reasons)

    return VerificationResult(
        verified=verified,
        safe_issues_before=safe_issues_before,
        fixes_applied=fixes_applied,
        safe_issues_after=len(remaining),
        author_action_issues=author_action_issues,
        text_integrity_ok=text_integrity_ok,
        remaining_safe_rule_ids=remaining_ids,
        failure_reason=failure_reason,
        document_preservation_ok=document_preservation_ok,
        preservation_warnings=list(preservation_warnings or []),
    )
