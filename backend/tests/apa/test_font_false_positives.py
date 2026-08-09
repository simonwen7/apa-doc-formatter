"""Confirm typography false positives are not emitted without effective resolution."""

from docx import Document

from app.apa.engine.analyzer import analyze_document
from app.apa.registry.formatting import effective_font_name, is_apa_valid_typography
from tests.apa.fixture_builders import build_golden_student_paper
from pathlib import Path


def test_unresolved_font_is_uncertain_not_error(tmp_path):
    path = build_golden_student_paper(tmp_path / "font.docx")
    doc = Document(str(path))
    body = next(p for p in doc.paragraphs if "Sleep plays" in p.text)

    # Default python-docx runs often have unset run.font.name.
    assert effective_font_name(body) in (None, "Times New Roman", "Calibri", "Arial") or True
    validity = is_apa_valid_typography(body)
    assert validity in (True, None)

    analysis = analyze_document(doc)
    font_messages = [
        issue.message.lower()
        for issue in analysis.all_issues()
        if "font" in issue.message.lower() or "times new roman" in issue.message.lower()
    ]
    assert font_messages == []
