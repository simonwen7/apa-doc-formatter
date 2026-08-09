from pathlib import Path

import pytest

from tests.apa.fixture_builders import (
    FIXTURES_DIR,
    build_failing_phase2a_paper,
    build_golden_student_paper,
)


@pytest.fixture(scope="session")
def golden_docx() -> Path:
    path = FIXTURES_DIR / "golden_apa7_student.docx"
    return build_golden_student_paper(path)


@pytest.fixture(scope="session")
def failing_docx() -> Path:
    path = FIXTURES_DIR / "failing_phase2a.docx"
    return build_failing_phase2a_paper(path)
