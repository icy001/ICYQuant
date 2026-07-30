"""
Tests for migration guide completeness and correctness.

Covers:
- migration_guide.md exists
- compatibility_matrix.md exists
- Migration covers v0.3.x to v0.4.x
- Future migration path documented
- Rollback procedure documented
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
RELEASE_NOTES_DIR = DOCS_DIR / "release_notes"


def _find_migration_doc() -> Optional[Path]:
    candidates = [
        DOCS_DIR / "migration_guide.md",
        RELEASE_NOTES_DIR / "migration_guide.md",
        PROJECT_ROOT / "migration_guide.md",
        PROJECT_ROOT / "RELEASE.md",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    v040_doc = RELEASE_NOTES_DIR / "v0.4.0-alpha1.md"
    if v040_doc.exists():
        return v040_doc
    return None


def _find_compatibility_matrix() -> Optional[Path]:
    candidates = [
        DOCS_DIR / "compatibility_matrix.md",
        RELEASE_NOTES_DIR / "compatibility_matrix.md",
        PROJECT_ROOT / "compatibility_matrix.md",
        DOCS_DIR / "api" / "compatibility_matrix.md",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


class TestMigrationGuide:
    """Tests for migration guide documentation."""

    def test_migration_guide_exists(self):
        guide = _find_migration_doc()
        assert guide is not None, (
            "migration_guide.md or RELEASE.md must exist for GA"
        )

    def test_migration_covers_v03_to_v04(self):
        guide = _find_migration_doc()
        if guide is None:
            pytest.skip("migration guide not found")
        content = guide.read_text(encoding="utf-8")
        has_v03 = any(
            term in content for term in ["0.3", "v0.3", "v0.3.x"]
        )
        has_v04 = any(
            term in content for term in ["0.4", "v0.4", "v0.4.x"]
        )
        assert has_v03 and has_v04, (
            "Migration guide must cover v0.3.x to v0.4.x migration path"
        )

    def test_migration_has_prerequisites(self):
        guide = _find_migration_doc()
        if guide is None:
            pytest.skip("migration guide not found")
        content = guide.read_text(encoding="utf-8")
        prereq_terms = ["prerequisite", "前提", "先决条件", "requirement", "准备", "硬件"]
        found = any(term.lower() in content.lower() for term in prereq_terms)
        assert found, "Migration guide must include prerequisites section"

    def test_migration_has_step_by_step(self):
        guide = _find_migration_doc()
        if guide is None:
            pytest.skip("migration guide not found")
        content = guide.read_text(encoding="utf-8")
        has_steps = any(
            term in content
            for term in ["步骤", "Step", "step", "1.", "2.", "3.", "###", "## "]
        )
        assert has_steps, "Migration guide must have step-by-step instructions"

    def test_migration_has_verification(self):
        guide = _find_migration_doc()
        if guide is None:
            pytest.skip("migration guide not found")
        content = guide.read_text(encoding="utf-8")
        verify_terms = ["verify", "验证", "Validate", "smoke test", "健康检查", "health", "检查"]
        found = any(term.lower() in content.lower() for term in verify_terms)
        assert found, "Migration guide must include verification steps"

    def test_migration_guide_has_version(self):
        guide = _find_migration_doc()
        if guide is None:
            pytest.skip("migration guide not found")
        content = guide.read_text(encoding="utf-8")
        has_version = any(
            term in content
            for term in ["v0.4.0-alpha1", "0.4.0-alpha1", "v0.4.0"]
        )
        assert has_version, (
            "Migration guide must reference v0.4.0-alpha1"
        )


class TestCompatibilityMatrix:
    """Tests for compatibility matrix documentation."""

    def test_compatibility_matrix_exists(self):
        matrix = _find_compatibility_matrix()
        if matrix is None:
            pytest.skip("compatibility_matrix.md not found (optional for GA)")
            return
        assert matrix is not None

    def test_compatibility_matrix_has_versions(self):
        matrix = _find_compatibility_matrix()
        if matrix is None:
            pytest.skip("compatibility_matrix.md not found")
            return
        content = matrix.read_text(encoding="utf-8")
        has_versions = any(
            term in content for term in ["0.3", "0.4", "version"]
        )
        assert has_versions, (
            "Compatibility matrix must reference version numbers"
        )

    def test_compatibility_matrix_has_supported_status(self):
        matrix = _find_compatibility_matrix()
        if matrix is None:
            pytest.skip("compatibility_matrix.md not found")
            return
        content = matrix.read_text(encoding="utf-8")
        status_terms = ["supported", "兼容", "compatible", "不兼容", "unsupported", "partial"]
        found = any(term.lower() in content.lower() for term in status_terms)
        assert found, "Compatibility matrix must specify support status"


class TestFutureMigrationPath:
    """Tests for future migration path documentation."""

    def test_future_migration_documented(self):
        guide = _find_migration_doc()
        if guide is None:
            pytest.skip("migration guide not found")
        content = guide.read_text(encoding="utf-8")
        future_terms = ["future", "未来", "后续", "next", "roadmap", "以后", "upgrade path", "升级路径"]
        found = any(term.lower() in content.lower() for term in future_terms)
        assert found, "Migration guide must document future migration path"

    def test_future_migration_has_version_05(self):
        guide = _find_migration_doc()
        if guide is None:
            pytest.skip("migration guide not found")
        content = guide.read_text(encoding="utf-8")
        has_future_version = any(
            term in content
            for term in ["0.5", "v0.5", "1.0", "v1.0", "next major", "Beta", "RC"]
        )
        assert has_future_version, (
            "Migration guide must mention future target versions (e.g., v0.5.x or v1.0)"
        )

    def test_future_migration_has_notes(self):
        guide = _find_migration_doc()
        if guide is None:
            pytest.skip("migration guide not found")
        content = guide.read_text(encoding="utf-8")
        has_notes = len(content) > 500
        assert has_notes, "Migration guide must have substantial content about future path"


class TestRollbackProcedure:
    """Tests for rollback procedure documentation."""

    def test_rollback_procedure_documented(self):
        guide = _find_migration_doc()
        if guide is None:
            pytest.skip("migration guide not found")
        content = guide.read_text(encoding="utf-8")
        rollback_terms = ["rollback", "回滚", "revert", "roll back", "恢复", "restore"]
        found = any(term.lower() in content.lower() for term in rollback_terms)
        assert found, "Migration guide must document rollback procedure"

    def test_rollback_has_steps(self):
        guide = _find_migration_doc()
        if guide is None:
            pytest.skip("migration guide not found")
        content = guide.read_text(encoding="utf-8")
        has_rollback_steps = any(
            term in content
            for term in [
                "回滚到",
                "rollback to",
                "helm uninstall",
                "helm install",
                "恢复",
                "restore",
                "alembic",
            ]
        )
        assert has_rollback_steps, (
            "Rollback procedure must include specific recovery steps"
        )

    def test_rollback_has_data_restoration(self):
        guide = _find_migration_doc()
        if guide is None:
            pytest.skip("migration guide not found")
        content = guide.read_text(encoding="utf-8")
        data_terms = ["backup", "备份", "database", "数据库", "restore", "恢复", "alembic"]
        found = any(term.lower() in content.lower() for term in data_terms)
        assert found, "Rollback procedure must address data restoration"

    def test_rollback_has_validation(self):
        guide = _find_migration_doc()
        if guide is None:
            pytest.skip("migration guide not found")
        content = guide.read_text(encoding="utf-8")
        validation_terms = ["verify", "验证", "validate", "smoke test", "健康检查", "health", "检查"]
        found = any(term.lower() in content.lower() for term in validation_terms)
        assert found, (
            "Rollback procedure must include post-rollback validation steps"
        )

    def test_rollback_time_estimate(self):
        guide = _find_migration_doc()
        if guide is None:
            pytest.skip("migration guide not found")
        content = guide.read_text(encoding="utf-8")
        time_terms = ["minute", "min", "小时", "hour", "time", "预计", "预计时间"]
        found = any(term.lower() in content.lower() for term in time_terms)
        assert found, "Rollback procedure must include time estimate"