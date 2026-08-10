from pathlib import Path
import hashlib
import shutil

import pytest

from tests.apa.fixture_builders import (
    FIXTURES_DIR,
    build_failing_phase2a_paper,
    build_golden_student_paper,
)


def _materialize_canonical_fixture(
    *,
    canonical_name: str,
    session_tmp: Path,
    builder,
) -> Path:
    """
    Provide a writable working copy of a canonical fixture.

    Canonical files under tests/apa/fixtures/ are never overwritten by tests.
    If a committed fixture exists, it is copied into the session temp dir.
    Otherwise a disposable fixture is generated only in the temp dir.
    """
    canonical = FIXTURES_DIR / canonical_name
    target = session_tmp / canonical_name
    target.parent.mkdir(parents=True, exist_ok=True)
    if canonical.exists():
        shutil.copy2(canonical, target)
        return target
    return builder(target)


@pytest.fixture(scope="session")
def _apa_fixture_workspace(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("apa_canonical_fixtures")


@pytest.fixture(scope="session")
def golden_docx(_apa_fixture_workspace: Path) -> Path:
    return _materialize_canonical_fixture(
        canonical_name="golden_apa7_student.docx",
        session_tmp=_apa_fixture_workspace,
        builder=build_golden_student_paper,
    )


@pytest.fixture(scope="session")
def failing_docx(_apa_fixture_workspace: Path) -> Path:
    return _materialize_canonical_fixture(
        canonical_name="failing_phase2a.docx",
        session_tmp=_apa_fixture_workspace,
        builder=build_failing_phase2a_paper,
    )


@pytest.fixture(scope="session")
def canonical_fixture_fingerprints() -> dict[str, str]:
    """SHA-256 of committed fixture binaries for immutability checks."""
    fingerprints: dict[str, str] = {}
    for path in sorted(FIXTURES_DIR.glob("*.docx")):
        fingerprints[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return fingerprints
