"""Equation detection / preservation helpers (Phase 2D). No content rewriting."""

from __future__ import annotations

from dataclasses import dataclass, field

from docx import Document


@dataclass
class EquationAnalysis:
    equation_index: int
    paragraph_index: int
    confidence: float
    evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def analyze_equations(doc: Document) -> list[EquationAnalysis]:
    analyses: list[EquationAnalysis] = []
    eq_index = 0
    for index, paragraph in enumerate(doc.paragraphs):
        try:
            xml = paragraph._p.xml
        except Exception:
            continue
        if "oMath" in xml or "oMathPara" in xml:
            analyses.append(
                EquationAnalysis(
                    equation_index=eq_index,
                    paragraph_index=index,
                    confidence=0.99,
                    evidence=["omml_present"],
                    warnings=["equation_content_not_auto_fixed"],
                )
            )
            eq_index += 1
    return analyses


def equation_xml_fingerprint(doc: Document) -> str:
    """Stable fingerprint of OMML fragments for preservation tests."""
    import hashlib

    chunks: list[str] = []
    try:
        xml = doc.element.body.xml
    except Exception:
        return ""
    # Keep only equation-ish substrings length for hash stability.
    for token in ("oMathPara", "oMath"):
        chunks.append(f"{token}:{xml.count(token)}")
    return hashlib.sha256("|".join(chunks).encode("utf-8")).hexdigest()
