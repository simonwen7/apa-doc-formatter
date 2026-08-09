from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Protocol

from docx import Document

from app.apa.engine.classifier import ClassifiedParagraph
from app.apa.models import Fixability, Issue, SourceRef
from app.apa.profile import DEFAULT_SAFE_CONFIDENCE, PROFILE_ID


@dataclass
class RuleContext:
    doc: Document
    classified: list[ClassifiedParagraph]
    template_id: str = PROFILE_ID
    reference_analyses: list = None  # type: ignore[assignment]
    citations: list = None  # type: ignore[assignment]
    match_results: list = None  # type: ignore[assignment]
    table_analyses: list = None  # type: ignore[assignment]
    figure_analyses: list = None  # type: ignore[assignment]
    appendix_analyses: list = None  # type: ignore[assignment]
    list_analyses: list = None  # type: ignore[assignment]
    equation_analyses: list = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.reference_analyses is None:
            self.reference_analyses = []
        if self.citations is None:
            self.citations = []
        if self.match_results is None:
            self.match_results = []
        if self.table_analyses is None:
            self.table_analyses = []
        if self.figure_analyses is None:
            self.figure_analyses = []
        if self.appendix_analyses is None:
            self.appendix_analyses = []
        if self.list_analyses is None:
            self.list_analyses = []
        if self.equation_analyses is None:
            self.equation_analyses = []


class Rule(Protocol):
    rule_id: str
    profile: str
    category: str
    description: str
    official_expectation: str
    source: SourceRef
    fixability: Fixability
    applicable_regions: tuple[str, ...]
    minimum_confidence: float
    severity: str
    production_supported: bool

    def detect(self, context: RuleContext) -> list[Issue]:
        ...

    def apply_fix(self, context: RuleContext, issue: Issue) -> bool:
        ...


@dataclass
class BaseRule:
    rule_id: str
    category: str
    description: str
    official_expectation: str
    source: SourceRef
    fixability: Fixability
    applicable_regions: tuple[str, ...]
    detector: Callable[[RuleContext], list[Issue]]
    fixer: Optional[Callable[[RuleContext, Issue], bool]] = None
    profile: str = PROFILE_ID
    minimum_confidence: float = DEFAULT_SAFE_CONFIDENCE
    severity: str = "error"
    production_supported: bool = False
    # Coverage flags for reporting
    detector_implemented: bool = True
    fixer_implemented: bool = False
    passing_fixture: bool = False
    failing_fixture: bool = False
    detector_test: bool = False
    fixer_test: bool = False
    post_fix_test: bool = False
    text_integrity_test: bool = False
    idempotency_test: bool = False
    preservation_test: bool = False

    def detect(self, context: RuleContext) -> list[Issue]:
        return self.detector(context)

    def apply_fix(self, context: RuleContext, issue: Issue) -> bool:
        if self.fixability != Fixability.SAFE_AUTO_FIX:
            return False
        if self.fixer is None:
            return False
        if issue.confidence < self.minimum_confidence:
            return False
        return bool(self.fixer(context, issue))
