from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class Fixability(str, Enum):
    SAFE_AUTO_FIX = "SAFE_AUTO_FIX"
    AUTHOR_ACTION_REQUIRED = "AUTHOR_ACTION_REQUIRED"
    CONDITIONAL = "CONDITIONAL"
    UNSUPPORTED = "UNSUPPORTED"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Region(str, Enum):
    TITLE_PAGE = "TITLE_PAGE"
    PAPER_TITLE = "PAPER_TITLE"
    BODY = "BODY"
    BODY_TITLE = "BODY_TITLE"
    HEADING = "HEADING"
    LEVEL_1_HEADING = "LEVEL_1_HEADING"
    LEVEL_2_HEADING = "LEVEL_2_HEADING"
    LEVEL_3_HEADING = "LEVEL_3_HEADING"
    LEVEL_4_HEADING = "LEVEL_4_HEADING"
    LEVEL_5_HEADING = "LEVEL_5_HEADING"
    ABSTRACT = "ABSTRACT"
    ABSTRACT_HEADING = "ABSTRACT_HEADING"
    KEYWORDS = "KEYWORDS"
    BLOCK_QUOTE = "BLOCK_QUOTE"
    TABLE = "TABLE"
    TABLE_NUMBER = "TABLE_NUMBER"
    TABLE_TITLE = "TABLE_TITLE"
    TABLE_CAPTION = "TABLE_CAPTION"
    TABLE_NOTE = "TABLE_NOTE"
    TABLE_GENERAL_NOTE = "TABLE_GENERAL_NOTE"
    TABLE_SPECIFIC_NOTE = "TABLE_SPECIFIC_NOTE"
    TABLE_PROBABILITY_NOTE = "TABLE_PROBABILITY_NOTE"
    FIGURE = "FIGURE"
    FIGURE_NUMBER = "FIGURE_NUMBER"
    FIGURE_TITLE = "FIGURE_TITLE"
    FIGURE_CAPTION = "FIGURE_CAPTION"
    FIGURE_NOTE = "FIGURE_NOTE"
    FIGURE_LEGEND = "FIGURE_LEGEND"
    REFERENCES_HEADING = "REFERENCES_HEADING"
    REFERENCE_ENTRY = "REFERENCE_ENTRY"
    APPENDIX = "APPENDIX"
    APPENDIX_LABEL = "APPENDIX_LABEL"
    APPENDIX_TITLE = "APPENDIX_TITLE"
    APPENDIX_BODY = "APPENDIX_BODY"
    LIST_ITEM = "LIST_ITEM"
    OTHER_SECTION_LABEL = "OTHER_SECTION_LABEL"
    HEADER = "HEADER"
    FOOTER = "FOOTER"
    UNKNOWN = "UNKNOWN"


# Specialized regions that must never receive generic BODY formatting fixes.
SPECIALIZED_REGIONS = frozenset(
    {
        Region.TITLE_PAGE,
        Region.PAPER_TITLE,
        Region.BODY_TITLE,
        Region.HEADING,
        Region.LEVEL_1_HEADING,
        Region.LEVEL_2_HEADING,
        Region.LEVEL_3_HEADING,
        Region.LEVEL_4_HEADING,
        Region.LEVEL_5_HEADING,
        Region.ABSTRACT,
        Region.ABSTRACT_HEADING,
        Region.KEYWORDS,
        Region.BLOCK_QUOTE,
        Region.TABLE,
        Region.TABLE_NUMBER,
        Region.TABLE_TITLE,
        Region.TABLE_CAPTION,
        Region.TABLE_NOTE,
        Region.TABLE_GENERAL_NOTE,
        Region.TABLE_SPECIFIC_NOTE,
        Region.TABLE_PROBABILITY_NOTE,
        Region.FIGURE,
        Region.FIGURE_NUMBER,
        Region.FIGURE_TITLE,
        Region.FIGURE_CAPTION,
        Region.FIGURE_NOTE,
        Region.FIGURE_LEGEND,
        Region.REFERENCES_HEADING,
        Region.REFERENCE_ENTRY,
        Region.APPENDIX,
        Region.APPENDIX_LABEL,
        Region.APPENDIX_TITLE,
        Region.APPENDIX_BODY,
        Region.LIST_ITEM,
        Region.OTHER_SECTION_LABEL,
        Region.HEADER,
        Region.FOOTER,
    }
)

@dataclass(frozen=True)
class SourceRef:
    official_resource: str
    publication_manual_section: Optional[str] = None
    notes: Optional[str] = None
    source_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Issue:
    rule_id: str
    category: str
    message: str
    expected: str
    actual: str
    location: str
    severity: Severity
    fixability: Fixability
    can_fix: bool
    confidence: float
    source: SourceRef
    reason_not_fixable: Optional[str] = None
    paragraph_index: Optional[int] = None
    section_index: Optional[int] = None
    region: Region = Region.UNKNOWN
    # Phase 2C optional metadata (never include full document text).
    citation_index: Optional[int] = None
    reference_index: Optional[int] = None
    reference_type: Optional[str] = None
    match_status: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "rule_id": self.rule_id,
            "category": self.category,
            "message": self.message,
            "expected": self.expected,
            "actual": self.actual,
            "location": self.location,
            "severity": self.severity.value,
            "fixability": self.fixability.value,
            "user_group": self.fixability.value,
            "can_fix": self.can_fix,
            "confidence": self.confidence,
            "source": self.source.to_dict(),
            "reason_not_fixable": self.reason_not_fixable,
            "paragraph_index": self.paragraph_index,
            "section_index": self.section_index,
            "region": self.region.value,
            "citation_index": self.citation_index,
            "reference_index": self.reference_index,
            "reference_type": self.reference_type,
            "match_status": self.match_status,
        }
        return payload

    def to_legacy_dict(self) -> dict[str, str]:
        """Backward-compatible issue shape for existing frontend."""
        return {
            "category": self.category,
            "message": self.message,
        }


@dataclass
class AnalysisResult:
    template_id: str
    safe_auto_fix: list[Issue] = field(default_factory=list)
    author_action_required: list[Issue] = field(default_factory=list)
    uncertain: list[Issue] = field(default_factory=list)
    unsupported: list[Issue] = field(default_factory=list)

    @property
    def safe_fix_count(self) -> int:
        return len(self.safe_auto_fix)

    @property
    def author_action_count(self) -> int:
        return len(self.author_action_required)

    @property
    def formatting_compliance_score(self) -> int:
        """FORMATTING compliance only (not overall APA correctness).

        Score decreases solely with outstanding SAFE_AUTO_FIX issues.
        AUTHOR_ACTION_REQUIRED / CONDITIONAL / UNSUPPORTED issues do not
        reduce this score and must not be presented as "APA perfect."
        """
        return max(0, 100 - self.safe_fix_count * 2)

    @property
    def citation_warning_count(self) -> int:
        return sum(
            1
            for issue in self.author_action_required
            if issue.category.lower() in {"citations", "citation matching", "quotations"}
            or issue.rule_id.startswith("APA7-CITATION")
            or issue.rule_id.startswith("APA7-MATCH")
            or issue.rule_id.startswith("APA7-QUOTE")
        )

    @property
    def reference_content_warning_count(self) -> int:
        return sum(
            1
            for issue in self.author_action_required
            if issue.category.lower() in {"reference content", "references content"}
            or issue.rule_id.startswith("APA7-REFCONTENT")
            or issue.rule_id.startswith("APA7-REFERENCE-ORDER")
            or issue.rule_id.startswith("APA7-REFERENCE-ALPHA")
        )

    def all_issues(self) -> list[Issue]:
        return (
            self.safe_auto_fix
            + self.author_action_required
            + self.uncertain
            + self.unsupported
        )

    def dedupe_key(self, issue: Issue) -> tuple:
        return (
            issue.rule_id,
            issue.paragraph_index,
            issue.section_index,
            issue.location,
            issue.message,
        )

    def to_api_dict(self) -> dict[str, Any]:
        legacy_issues = [issue.to_legacy_dict() for issue in self.all_issues()]
        return {
            "template_id": self.template_id,
            "safe_auto_fix": [issue.to_dict() for issue in self.safe_auto_fix],
            "author_action_required": [
                issue.to_dict() for issue in self.author_action_required
            ],
            "uncertain": [issue.to_dict() for issue in self.uncertain],
            "unsupported": [issue.to_dict() for issue in self.unsupported],
            "summary": {
                "safe_fix_count": self.safe_fix_count,
                "author_action_count": self.author_action_count,
                "formatting_compliance_score": self.formatting_compliance_score,
                "formatting_safe_issue_count": self.safe_fix_count,
                "citation_warning_count": self.citation_warning_count,
                "reference_content_warning_count": self.reference_content_warning_count,
                # Compatibility with existing frontend fields:
                "score": self.formatting_compliance_score,
                "issue_count": self.safe_fix_count + self.author_action_count,
                # Explicit naming so clients do not treat score as overall APA correctness.
                "score_scope": "formatting_safe_auto_fix_only",
            },
            # Compatibility: existing UI groups by category/message.
            "issues": legacy_issues,
        }


@dataclass
class VerificationResult:
    verified: bool
    safe_issues_before: int
    fixes_applied: int
    safe_issues_after: int
    author_action_issues: int
    text_integrity_ok: bool
    remaining_safe_rule_ids: list[str] = field(default_factory=list)
    failure_reason: Optional[str] = None
    document_preservation_ok: bool = True
    preservation_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
