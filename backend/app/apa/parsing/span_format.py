"""Safe character-span formatting over existing runs (no text mutation)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from docx.text.paragraph import Paragraph


@dataclass
class SpanFormatResult:
    applied: bool
    unsafe_to_format: bool
    reason: Optional[str] = None


def _paragraph_has_unsupported_objects(paragraph: Paragraph) -> bool:
    try:
        xml = paragraph._p.xml
    except Exception:
        return True
    if "w:hyperlink" in xml or "w:fldChar" in xml or "w:fldSimple" in xml:
        return True
    if "w:bookmarkStart" in xml:
        return True
    return False


def can_format_existing_text_span(
    paragraph: Paragraph,
    start_char: int,
    end_char: int,
) -> SpanFormatResult:
    """Dry-run check: whether a span is safely formatable (no mutation)."""
    if start_char < 0 or end_char <= start_char:
        return SpanFormatResult(False, True, "invalid_span")

    full = paragraph.text or ""
    if end_char > len(full):
        return SpanFormatResult(False, True, "span_out_of_range")

    if _paragraph_has_unsupported_objects(paragraph):
        return SpanFormatResult(False, True, "unsupported_objects")

    mapping = []
    cursor = 0
    for run in paragraph.runs:
        text = run.text or ""
        mapping.append((run, cursor, cursor + len(text), text))
        cursor += len(text)

    joined = "".join(t for _r, _s, _e, t in mapping)
    if joined != full:
        return SpanFormatResult(False, True, "run_text_mismatch")

    covered = 0
    for _run, start, end, _text in mapping:
        if end <= start_char or start >= end_char:
            continue
        if start < start_char or end > end_char:
            return SpanFormatResult(False, True, "span_not_run_aligned")
        covered += end - start

    if covered != (end_char - start_char) or covered == 0:
        return SpanFormatResult(False, True, "incomplete_coverage")
    return SpanFormatResult(False, False, "ok")


def apply_format_to_existing_text_span(
    paragraph: Paragraph,
    start_char: int,
    end_char: int,
    *,
    italic: Optional[bool] = None,
    bold: Optional[bool] = None,
) -> SpanFormatResult:
    """
    Apply formatting only when the span aligns to one or more *complete* runs.

    No run splitting. No character changes. Hyperlinks/fields/bookmarks => unsafe.
    """
    if start_char < 0 or end_char <= start_char:
        return SpanFormatResult(False, True, "invalid_span")

    full = paragraph.text or ""
    if end_char > len(full):
        return SpanFormatResult(False, True, "span_out_of_range")

    if _paragraph_has_unsupported_objects(paragraph):
        return SpanFormatResult(False, True, "unsupported_objects")

    mapping = []
    cursor = 0
    for run in paragraph.runs:
        text = run.text or ""
        mapping.append((run, cursor, cursor + len(text), text))
        cursor += len(text)

    joined = "".join(t for _r, _s, _e, t in mapping)
    if joined != full:
        return SpanFormatResult(False, True, "run_text_mismatch")

    target_runs = []
    covered = 0
    for run, start, end, _text in mapping:
        if end <= start_char or start >= end_char:
            continue
        # Must cover the run entirely within the target span.
        if start < start_char or end > end_char:
            return SpanFormatResult(False, True, "span_not_run_aligned")
        target_runs.append(run)
        covered += end - start

    if covered != (end_char - start_char) or not target_runs:
        return SpanFormatResult(False, True, "incomplete_coverage")

    before = paragraph.text
    for run in target_runs:
        if italic is not None:
            run.font.italic = italic
        if bold is not None:
            run.font.bold = bold
    if paragraph.text != before:
        return SpanFormatResult(False, True, "text_changed")
    return SpanFormatResult(True, False, None)
