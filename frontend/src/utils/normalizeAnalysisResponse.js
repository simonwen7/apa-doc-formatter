/**
 * Normalize analyze/fix API responses into a stable frontend model.
 * Trusts backend fixability — does not re-decide SAFE vs AUTHOR.
 */

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function asNumber(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function normalizeIssue(raw, fallbackGroup = "AUTHOR_ACTION_REQUIRED") {
  if (!raw || typeof raw !== "object") {
    return null;
  }

  const fixability =
    raw.fixability ||
    raw.user_group ||
    fallbackGroup;

  return {
    ruleId: raw.rule_id || raw.ruleId || null,
    category: raw.category || "Other",
    userGroup: raw.user_group || fixability,
    fixability,
    canFix: Boolean(raw.can_fix),
    message: raw.message || "Review this item.",
    expected: raw.expected || "",
    actual: raw.actual || "",
    location: raw.location || "",
    severity: raw.severity || "warning",
    confidence: asNumber(raw.confidence, 0),
    reasonNotFixable: raw.reason_not_fixable || raw.reasonNotFixable || "",
    source: raw.source || null,
    paragraphIndex: raw.paragraph_index ?? raw.paragraphIndex ?? null,
    referenceIndex: raw.reference_index ?? raw.referenceIndex ?? null,
    citationIndex: raw.citation_index ?? raw.citationIndex ?? null,
    referenceType: raw.reference_type || raw.referenceType || null,
    matchStatus: raw.match_status || raw.matchStatus || null,
  };
}

function normalizeIssueList(list, fallbackGroup) {
  return asArray(list)
    .map((item) => normalizeIssue(item, fallbackGroup))
    .filter(Boolean);
}

/**
 * Group issues by category for display.
 */
export function groupIssuesByCategory(issues) {
  return asArray(issues).reduce((groups, issue) => {
    const category = issue.category || "Other";
    if (!groups[category]) {
      groups[category] = [];
    }
    groups[category].push(issue);
    return groups;
  }, {});
}

export function formattingFixButtonLabel(safeCount) {
  const n = asNumber(safeCount, 0);
  if (n <= 0) return "";
  if (n === 1) return "Fix 1 Formatting Issue";
  return `Fix ${n} Formatting Issues`;
}

export function getFormattingScoreLabel(score) {
  const s = asNumber(score, 0);
  if (s >= 90) return "Excellent formatting";
  if (s >= 70) return "Good formatting";
  if (s >= 40) return "Needs formatting improvement";
  return "Significant formatting changes needed";
}

export function getFormattingScoreTone(score) {
  const s = asNumber(score, 0);
  if (s >= 90) return "excellent";
  if (s >= 70) return "good";
  if (s >= 40) return "warning";
  return "poor";
}

/**
 * Normalize POST /documents/analyze (or validation_after_fix subset).
 */
export function normalizeAnalysisResponse(payload) {
  const summary = payload?.summary || {};

  const safeIssues = normalizeIssueList(
    payload?.safe_auto_fix,
    "SAFE_AUTO_FIX"
  );
  const authorIssues = normalizeIssueList(
    payload?.author_action_required,
    "AUTHOR_ACTION_REQUIRED"
  );
  const uncertainIssues = normalizeIssueList(
    payload?.uncertain,
    "CONDITIONAL"
  ).concat(normalizeIssueList(payload?.unsupported, "UNSUPPORTED"));

  // Prefer explicit summary counts from backend; fall back to array lengths.
  const safeCount =
    summary.safe_fix_count != null
      ? asNumber(summary.safe_fix_count)
      : safeIssues.length;
  const authorCount =
    summary.author_action_count != null
      ? asNumber(summary.author_action_count)
      : authorIssues.length;

  const formattingScore = Math.max(
    0,
    Math.min(
      100,
      asNumber(
        summary.formatting_compliance_score ?? summary.score,
        Math.max(0, 100 - safeCount * 2)
      )
    )
  );

  return {
    filename: payload?.filename || "",
    template: payload?.template || payload?.template_id || "",
    formattingScore,
    scoreScope:
      summary.score_scope || "formatting_safe_auto_fix_only",
    safeIssues,
    authorIssues,
    uncertainIssues,
    // Unsupported already folded into uncertainIssues for cautious display
    // when they appear as real document issues.
    unsupportedIssues: normalizeIssueList(
      payload?.unsupported,
      "UNSUPPORTED"
    ),
    safeCount,
    authorCount,
    uncertainCount: uncertainIssues.length,
    canFix: safeCount > 0,
    groupedSafeIssues: groupIssuesByCategory(safeIssues),
    groupedAuthorIssues: groupIssuesByCategory(authorIssues),
    groupedUncertainIssues: groupIssuesByCategory(uncertainIssues),
  };
}

/**
 * Normalize POST /documents/fix response.
 */
export function normalizeFixResponse(payload) {
  const verification = payload?.verification || {};
  const validationAfter = payload?.validation_after_fix || {};

  const analysisAfter = normalizeAnalysisResponse({
    ...validationAfter,
    filename: payload?.filename,
    template: payload?.template,
    // Prefer top-level author leftovers when present.
    author_action_required:
      payload?.author_action_required ??
      validationAfter.author_action_required,
    safe_auto_fix:
      payload?.safe_auto_fix_after ?? validationAfter.safe_auto_fix,
  });

  const verified = Boolean(verification.verified);
  const safeIssuesAfter = asNumber(
    verification.safe_issues_after,
    analysisAfter.safeCount
  );
  const textIntegrityOk = verification.text_integrity_ok !== false;
  const documentPreservationOk =
    verification.document_preservation_ok !== false;

  const formattingSucceeded =
    verified && safeIssuesAfter === 0 && textIntegrityOk && documentPreservationOk;

  return {
    // Never advertise a download when verification failed.
    downloadUrl: formattingSucceeded ? payload?.download_url || null : null,
    fixedCounts: payload?.fixed_counts || {},
    verification: {
      verified,
      safeIssuesBefore: asNumber(verification.safe_issues_before, 0),
      safeIssuesAfter,
      authorActionCount: asNumber(
        verification.author_action_issues ?? analysisAfter.authorCount,
        analysisAfter.authorCount
      ),
      textIntegrityOk,
      documentPreservationOk,
    },
    formattingSucceeded,
    remainingAuthorIssues: analysisAfter.authorIssues,
    remainingAuthorCount: analysisAfter.authorIssues.length,
    remainingUncertainIssues: analysisAfter.uncertainIssues,
    analysisAfter,
  };
}
