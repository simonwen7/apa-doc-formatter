import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  formattingFixButtonLabel,
  normalizeAnalysisResponse,
  normalizeFixResponse,
} from "./normalizeAnalysisResponse.js";

describe("normalizeAnalysisResponse", () => {
  it("splits safe and author and ignores author in canFix", () => {
    const model = normalizeAnalysisResponse({
      filename: "paper.docx",
      template: "apa7_student",
      summary: {
        score: 96,
        formatting_compliance_score: 96,
        safe_fix_count: 2,
        author_action_count: 5,
        issue_count: 7,
        score_scope: "formatting_safe_auto_fix_only",
      },
      safe_auto_fix: [
        {
          rule_id: "APA7-GLOBAL-001",
          category: "Page Setup",
          message: "Margins should be 1 inch.",
          fixability: "SAFE_AUTO_FIX",
          can_fix: true,
          expected: "1 in",
          actual: "0.75 in",
          location: "section[0]",
        },
        {
          rule_id: "APA7-BODY-001",
          category: "Body",
          message: "Indent body paragraphs.",
          fixability: "SAFE_AUTO_FIX",
          can_fix: true,
        },
      ],
      author_action_required: [
        {
          rule_id: "APA7-CITATION-ONE-AUTHOR",
          category: "Citations",
          message: "Review citation.",
          fixability: "AUTHOR_ACTION_REQUIRED",
          can_fix: false,
          reason_not_fixable: "Would modify text.",
        },
      ],
      uncertain: [],
      unsupported: [],
    });

    assert.equal(model.safeCount, 2);
    assert.equal(model.authorCount, 5);
    assert.equal(model.canFix, true);
    assert.equal(model.formattingScore, 96);
    assert.equal(model.safeIssues.length, 2);
    assert.equal(model.authorIssues.length, 1);
    assert.equal(formattingFixButtonLabel(model.safeCount), "Fix 2 Formatting Issues");
  });

  it("handles author-only (no Fix)", () => {
    const model = normalizeAnalysisResponse({
      summary: {
        score: 100,
        safe_fix_count: 0,
        author_action_count: 3,
      },
      safe_auto_fix: [],
      author_action_required: [
        { category: "Citations", message: "Review", fixability: "AUTHOR_ACTION_REQUIRED", can_fix: false },
      ],
      uncertain: [],
    });
    assert.equal(model.canFix, false);
    assert.equal(model.formattingScore, 100);
    assert.equal(formattingFixButtonLabel(model.safeCount), "");
  });

  it("handles no issues", () => {
    const model = normalizeAnalysisResponse({
      summary: { score: 100, safe_fix_count: 0, author_action_count: 0 },
      safe_auto_fix: [],
      author_action_required: [],
    });
    assert.equal(model.canFix, false);
    assert.equal(model.safeCount, 0);
    assert.equal(model.authorCount, 0);
  });

  it("treats uncertain cautiously", () => {
    const model = normalizeAnalysisResponse({
      summary: { score: 100, safe_fix_count: 0, author_action_count: 0 },
      safe_auto_fix: [],
      author_action_required: [],
      uncertain: [
        {
          category: "Citations",
          message: "et al. may need review",
          fixability: "CONDITIONAL",
          can_fix: false,
        },
      ],
    });
    assert.equal(model.uncertainCount, 1);
    assert.equal(model.canFix, false);
  });

  it("singular Fix label", () => {
    assert.equal(formattingFixButtonLabel(1), "Fix 1 Formatting Issue");
  });
});

describe("normalizeFixResponse", () => {
  it("marks verified success only when safe_after is 0", () => {
    const model = normalizeFixResponse({
      download_url: "/documents/download/abc",
      fixed_counts: { safe_rules_applied: 3 },
      verification: {
        verified: true,
        safe_issues_before: 3,
        safe_issues_after: 0,
        author_action_issues: 2,
        text_integrity_ok: true,
        document_preservation_ok: true,
      },
      author_action_required: [
        {
          category: "Citations",
          message: "Still needs review",
          fixability: "AUTHOR_ACTION_REQUIRED",
          can_fix: false,
        },
      ],
      validation_after_fix: {
        summary: { safe_fix_count: 0, author_action_count: 2, score: 100 },
        safe_auto_fix: [],
        author_action_required: [],
      },
    });

    assert.equal(model.formattingSucceeded, true);
    assert.equal(model.remainingAuthorCount, 1);
    assert.ok(model.downloadUrl);
  });

  it("fails when verified is false or safe_after != 0", () => {
    const failed = normalizeFixResponse({
      verification: {
        verified: false,
        safe_issues_after: 2,
        text_integrity_ok: true,
        document_preservation_ok: true,
      },
      validation_after_fix: { summary: {}, safe_auto_fix: [], author_action_required: [] },
    });
    assert.equal(failed.formattingSucceeded, false);

    const leftover = normalizeFixResponse({
      verification: {
        verified: true,
        safe_issues_after: 1,
        text_integrity_ok: true,
        document_preservation_ok: true,
      },
      validation_after_fix: { summary: {}, safe_auto_fix: [], author_action_required: [] },
    });
    assert.equal(leftover.formattingSucceeded, false);
  });
});
