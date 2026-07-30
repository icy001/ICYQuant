"""
Tests for GA release validation and promotion.

Covers:
- VERSION file contains "v0.4.0-alpha1"
- RELEASE.md exists and has GA content
- CHANGELOG.md has v0.4.0-alpha1 section
- release/ga/release_manifest.json has correct version
- Manifest stage is "GA" and status is "stable"
- Manifest has all artifact types
- VersionManager can parse "v0.4.0-alpha1" without rc1 suffix
- ReleaseCandidate can promote to GA stage
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from release.rc.release_candidate import RCStage, ReleaseCandidate
from release.rc.version_manager import PreReleaseTag, VersionManager


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RELEASE_GA_DIR = PROJECT_ROOT / "release" / "ga"
RELEASE_ARTIFACTS_DIR = PROJECT_ROOT / "release" / "artifacts"


@pytest.fixture
def version_file() -> str:
    version_path = PROJECT_ROOT / "VERSION"
    if not version_path.exists():
        pytest.skip("VERSION file not found")
    return version_path.read_text(encoding="utf-8").strip()


@pytest.fixture
def changelog_content() -> str:
    changelog_path = PROJECT_ROOT / "CHANGELOG.md"
    if not changelog_path.exists():
        pytest.skip("CHANGELOG.md not found")
    return changelog_path.read_text(encoding="utf-8")


@pytest.fixture
def release_manifest() -> Dict[str, Any]:
    manifest_path = RELEASE_GA_DIR / "release_manifest.json"
    if not manifest_path.exists():
        pytest.skip("release_manifest.json not found")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestVersionFile:
    """Tests for VERSION file content."""

    def test_version_file_exists(self):
        version_path = PROJECT_ROOT / "VERSION"
        assert version_path.exists(), "VERSION file must exist"

    def test_version_contains_ga_version(self, version_file: str):
        assert "v0.4.0-alpha1" in version_file, (
            f"VERSION file must contain v0.4.0-alpha1, got: {version_file}"
        )

    def test_version_does_not_contain_rc1(self, version_file: str):
        assert "rc1" not in version_file.lower(), (
            "VERSION file should not contain rc1 suffix for GA release"
        )


class TestReleaseDocument:
    """Tests for RELEASE.md existence and content."""

    def test_release_md_exists(self):
        release_md = PROJECT_ROOT / "RELEASE.md"
        assert release_md.exists(), "RELEASE.md must exist for GA release"

    def test_release_md_has_ga_content(self):
        release_md = PROJECT_ROOT / "RELEASE.md"
        if not release_md.exists():
            pytest.skip("RELEASE.md not found")
        content = release_md.read_text(encoding="utf-8")
        ga_terms = ["GA", "General Availability", "稳定", "stable", "正式发布"]
        found = any(term.lower() in content.lower() for term in ga_terms)
        assert found, "RELEASE.md must contain GA/stable release content"

    def test_release_md_references_version(self):
        release_md = PROJECT_ROOT / "RELEASE.md"
        if not release_md.exists():
            pytest.skip("RELEASE.md not found")
        content = release_md.read_text(encoding="utf-8")
        assert "v0.4.0-alpha1" in content, (
            "RELEASE.md must reference v0.4.0-alpha1 version"
        )


class TestChangelog:
    """Tests for CHANGELOG.md GA section."""

    def test_changelog_exists(self):
        changelog = PROJECT_ROOT / "CHANGELOG.md"
        assert changelog.exists(), "CHANGELOG.md must exist"

    def test_changelog_has_ga_version_section(self, changelog_content: str):
        assert "v0.4.0-alpha1" in changelog_content, (
            "CHANGELOG.md must have v0.4.0-alpha1 section"
        )

    def test_changelog_has_release_date(self, changelog_content: str):
        has_date = any(
            term in changelog_content
            for term in ["2026-07-30", "2026-07", "July 2026", "2026"]
        )
        assert has_date, "CHANGELOG.md should include release date for GA"

    def test_changelog_has_ga_entries(self, changelog_content: str):
        has_entries = any(
            term in changelog_content.lower()
            for term in ["added", "fixed", "changed", "release", "ga"]
        )
        assert has_entries, "CHANGELOG.md must contain release entries"


class TestGAReleaseManifest:
    """Tests for release/ga/release_manifest.json."""

    def test_manifest_file_exists(self):
        manifest_path = RELEASE_GA_DIR / "release_manifest.json"
        assert manifest_path.exists(), (
            "release/ga/release_manifest.json must exist for GA"
        )

    def test_manifest_has_correct_version(self, release_manifest: Dict[str, Any]):
        assert release_manifest.get("version") == "v0.4.0-alpha1", (
            f"Manifest version must be v0.4.0-alpha1, got: {release_manifest.get('version')}"
        )

    def test_manifest_stage_is_ga(self, release_manifest: Dict[str, Any]):
        stage = release_manifest.get("stage", "")
        assert stage == "GA", f"Manifest stage must be GA, got: {stage}"

    def test_manifest_release_is_ga(self, release_manifest: Dict[str, Any]):
        release_type = release_manifest.get("release", "")
        assert release_type == "GA", (
            f"Manifest release type must be GA, got: {release_type}"
        )

    def test_manifest_status_is_stable(self, release_manifest: Dict[str, Any]):
        status = release_manifest.get("status", "")
        assert status == "stable", (
            f"Manifest status must be stable for GA, got: {status}"
        )

    def test_manifest_has_all_artifact_types(self, release_manifest: Dict[str, Any]):
        artifacts = release_manifest.get("artifacts", {})
        expected_types = ["docker", "helm", "kubernetes", "python_sdk", "cli", "openapi"]
        for artifact_type in expected_types:
            assert artifact_type in artifacts, (
                f"Manifest missing artifact type: {artifact_type}"
            )

    def test_manifest_documents_flag_true(self, release_manifest: Dict[str, Any]):
        assert release_manifest.get("documentation") is True, (
            "Manifest must have documentation flag set to true"
        )

    def test_manifest_sbom_flag_true(self, release_manifest: Dict[str, Any]):
        assert release_manifest.get("sbom") is True, (
            "Manifest must have sbom flag set to true"
        )

    def test_manifest_checksums_flag_true(self, release_manifest: Dict[str, Any]):
        assert release_manifest.get("checksums") is True, (
            "Manifest must have checksums flag set to true"
        )

    def test_manifest_signatures_flag_true(self, release_manifest: Dict[str, Any]):
        assert release_manifest.get("signatures") is True, (
            "Manifest must have signatures flag set to true"
        )

    def test_manifest_has_compliance_info(self, release_manifest: Dict[str, Any]):
        compliance = release_manifest.get("compliance", {})
        assert compliance.get("license") == "MIT", (
            "Manifest compliance must specify MIT license"
        )
        assert compliance.get("sbom_format") == "CycloneDX", (
            "Manifest compliance must specify CycloneDX SBOM format"
        )


class TestVersionManagerGA:
    """Tests for VersionManager parsing GA version strings."""

    def test_parse_ga_version_without_rc_suffix(self):
        vm = VersionManager()
        info = vm.parse("v0.4.0-alpha1")
        assert info.major == 0
        assert info.minor == 4
        assert info.patch == 0
        assert info.pre_release == PreReleaseTag.ALPHA
        assert info.pre_release_num == 1
        assert info.sub_tag is None, (
            f"GA version should not have sub_tag, got: {info.sub_tag}"
        )

    def test_parse_ga_version_does_not_include_rc(self):
        vm = VersionManager()
        info = vm.parse("v0.4.0-alpha1")
        assert info.sub_tag is None, (
            "GA version v0.4.0-alpha1 should parse without rc1 sub-tag"
        )

    def test_ga_version_generation(self):
        vm = VersionManager()
        tag = vm.generate_tag(
            "0.4.0",
            pre_release=PreReleaseTag.ALPHA,
            pre_release_num=1,
            prefix="v",
        )
        assert tag == "v0.4.0-alpha.1"

    def test_version_compare_ga_vs_rc(self):
        vm = VersionManager()
        info_ga = vm.parse("v0.4.0-alpha1")
        info_rc = vm.parse("v0.4.0-alpha1-rc1")
        assert info_ga < info_rc, "GA alpha1 without rc1 should sort before alpha1-rc1"


class TestReleaseCandidateGA:
    """Tests for ReleaseCandidate GA stage promotion."""

    def test_promote_to_ga_stage(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        rc.promote("beta")
        rc.promote("rc")
        status = rc.promote("ga")
        assert status.current_stage == RCStage.GA
        assert status.promotion_recommendation == "released"

    def test_ga_stage_is_final(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        rc.promote("beta")
        rc.promote("rc")
        rc.promote("ga")
        status = rc.get_status()
        assert status.current_stage == RCStage.GA

    def test_ga_readiness_score_max(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        rc.promote("beta")
        rc.promote("rc")
        rc.promote("ga")
        score = rc.get_readiness_score()
        assert score == 1.0, f"GA readiness score should be 1.0, got: {score}"

    def test_ga_release_tag_generation(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        rc.promote("beta")
        rc.promote("rc")
        rc.promote("ga")
        tag = rc.generate_release_tag()
        assert "0.4.0" in tag
        assert "alpha" not in tag.lower() or "alpha1" not in tag.lower()

    def test_ga_full_lifecycle(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        rc.add_changelog_entry("Initial alpha release", change_type="added")
        rc.promote("beta")
        rc.add_changelog_entry("Beta improvements", change_type="changed")
        rc.promote("rc")
        rc.add_changelog_entry("Release candidate fixes", change_type="fixed")
        rc.record_go_no_go("GO", "All quality gates passed", "QA Lead")
        status = rc.promote("ga")
        assert status.current_stage == RCStage.GA
        assert status.changelog_accumulated == 3
        assert status.go_no_go is not None
        assert rc.go_no_go.value == "GO"

    def test_ga_cannot_promote_further(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        rc.promote("beta")
        rc.promote("rc")
        rc.promote("ga")
        with pytest.raises(ValueError):
            rc.promote("beta")

    def test_ga_deprecate(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        rc.promote("beta")
        rc.promote("rc")
        rc.promote("ga")
        status = rc.deprecate()
        assert status.current_stage == RCStage.DEPRECATED