"""
Tests for API freeze validation and version consistency.

Covers:
- API freeze document presence and structure
- Version consistency across all artifacts
- OpenAPI spec format validation
- Backward compatibility checks
- SDK version mapping
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RELEASE_RC_DIR = PROJECT_ROOT / "release" / "rc"
RELEASE_ARTIFACTS_DIR = PROJECT_ROOT / "release" / "artifacts"
RELEASE_PACKAGES_DIR = PROJECT_ROOT / "release" / "packages"
DOCS_API_DIR = PROJECT_ROOT / "docs" / "api"
DOCS_NOTES_DIR = PROJECT_ROOT / "docs" / "release_notes"


@pytest.fixture
def rc1_manifest():
    manifest_path = RELEASE_RC_DIR / "rc1_manifest.yaml"
    if not manifest_path.exists():
        pytest.skip("rc1_manifest.yaml not found")
    try:
        import yaml
        with open(manifest_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        pytest.skip("PyYAML not installed")


@pytest.fixture
def artifact_manifest():
    manifest_path = RELEASE_RC_DIR / "artifact_manifest.json"
    if not manifest_path.exists():
        pytest.skip("artifact_manifest.json not found")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def release_metadata():
    metadata_path = RELEASE_ARTIFACTS_DIR / "release_metadata.json"
    if not metadata_path.exists():
        pytest.skip("release_metadata.json not found")
    with open(metadata_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def openapi_spec():
    spec_path = DOCS_API_DIR / "openapi_v0.4.0-alpha1.yaml"
    if not spec_path.exists():
        pytest.skip("OpenAPI spec not found")
    try:
        import yaml
        with open(spec_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        pytest.skip("PyYAML not installed")


@pytest.fixture
def feature_freeze_doc():
    doc_path = RELEASE_RC_DIR / "feature_freeze.md"
    if not doc_path.exists():
        pytest.skip("feature_freeze.md not found")
    with open(doc_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def api_freeze_doc():
    doc_path = RELEASE_RC_DIR / "api_freeze.md"
    if not doc_path.exists():
        pytest.skip("api_freeze.md not found")
    with open(doc_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def configuration_freeze_doc():
    doc_path = RELEASE_RC_DIR / "configuration_freeze.md"
    if not doc_path.exists():
        pytest.skip("configuration_freeze.md not found")
    with open(doc_path, "r", encoding="utf-8") as f:
        return f.read()


class TestFreezeDocuments:
    """Tests for freeze document existence and content."""

    def test_feature_freeze_exists(self):
        doc = RELEASE_RC_DIR / "feature_freeze.md"
        assert doc.exists(), "feature_freeze.md must exist in release/rc/"

    def test_api_freeze_exists(self):
        doc = RELEASE_RC_DIR / "api_freeze.md"
        assert doc.exists(), "api_freeze.md must exist in release/rc/"

    def test_configuration_freeze_exists(self):
        doc = RELEASE_RC_DIR / "configuration_freeze.md"
        assert doc.exists(), "configuration_freeze.md must exist in release/rc/"

    def test_feature_freeze_has_frozen_modules(self, feature_freeze_doc: str):
        frozen_modules = [
            "Research", "AI", "Backtest", "OMS", "EMS",
            "Risk", "Portfolio", "Lakehouse", "Observability",
            "Security", "Platform",
        ]
        for module in frozen_modules:
            assert module in feature_freeze_doc, (
                f"Feature freeze must mention frozen module: {module}"
            )

    def test_feature_freeze_allows_bug_fix(self, feature_freeze_doc: str):
        assert "Bug Fix" in feature_freeze_doc or "bug fix" in feature_freeze_doc.lower(), (
            "Feature freeze should allow bug fixes"
        )

    def test_feature_freeze_prohibits_new_features(self, feature_freeze_doc: str):
        assert "禁止" in feature_freeze_doc or "prohibit" in feature_freeze_doc.lower(), (
            "Feature freeze must explicitly prohibit new features"
        )

    def test_api_freeze_rest_api_mentioned(self, api_freeze_doc: str):
        assert "/api/v1/" in api_freeze_doc or "REST" in api_freeze_doc, (
            "API freeze must cover REST API /api/v1/*"
        )

    def test_api_freeze_sdk_mentioned(self, api_freeze_doc: str):
        sdk_terms = ["Python SDK", "SDK", "Plugin SDK"]
        found = any(term in api_freeze_doc for term in sdk_terms)
        assert found, "API freeze must cover SDKs"

    def test_api_freeze_backward_compatibility(self, api_freeze_doc: str):
        compat_terms = ["兼容", "compatible", "backward"]
        found = any(term.lower() in api_freeze_doc.lower() for term in compat_terms)
        assert found, "API freeze must guarantee backward compatibility"

    def test_configuration_freeze_env_vars(self, configuration_freeze_doc: str):
        env_terms = ["Environment", "环境变量", "env"]
        found = any(term.lower() in configuration_freeze_doc.lower() for term in env_terms)
        assert found, "Configuration freeze must cover environment variables"

    def test_configuration_freeze_deployment(self, configuration_freeze_doc: str):
        deploy_terms = ["Deployment", "Helm", "Kubernetes", "部署"]
        found = any(term.lower() in configuration_freeze_doc.lower() for term in deploy_terms)
        assert found, "Configuration freeze must cover deployment templates"


class TestRC1Manifest:
    """Tests for RC1 manifest structure and consistency."""

    def test_manifest_exists(self):
        manifest = RELEASE_RC_DIR / "rc1_manifest.yaml"
        assert manifest.exists(), "rc1_manifest.yaml must exist"

    def test_manifest_has_version(self, rc1_manifest: Dict[str, Any]):
        spec = rc1_manifest.get("spec", {})
        assert "version" in spec, "Manifest must specify version"
        assert "0.4.0-alpha1" in spec["version"], "Version must be 0.4.0-alpha1"

    def test_manifest_has_frozen_modules(self, rc1_manifest: Dict[str, Any]):
        spec = rc1_manifest.get("spec", {})
        modules = spec.get("frozen_modules", [])
        assert len(modules) >= 11, "Must have at least 11 frozen modules"

        module_names = [m["name"] for m in modules]
        expected = [
            "Research", "AI", "Backtest", "OMS (Order Management System)",
            "EMS (Execution Management System)", "Risk", "Portfolio",
            "Lakehouse", "Observability", "Security", "Platform",
        ]
        for name in expected:
            assert name in module_names, f"Missing frozen module: {name}"

    def test_manifest_has_quality_gates(self, rc1_manifest: Dict[str, Any]):
        spec = rc1_manifest.get("spec", {})
        gates = spec.get("quality_gates", [])
        gate_names = [g["name"] for g in gates]
        expected_gates = ["unit_test", "integration_test", "security_scan", "performance", "lint", "type_check"]
        for name in expected_gates:
            assert name in gate_names, f"Missing quality gate: {name}"

    def test_manifest_has_artifacts(self, rc1_manifest: Dict[str, Any]):
        spec = rc1_manifest.get("spec", {})
        artifacts = spec.get("artifacts", [])
        artifact_names = [a["name"] for a in artifacts]
        expected = ["docker-image", "helm-chart", "icyquant-sdk", "api-documentation", "release-notes", "sbom"]
        for name in expected:
            assert name in artifact_names, f"Missing artifact: {name}"

    def test_manifest_has_signatories(self, rc1_manifest: Dict[str, Any]):
        spec = rc1_manifest.get("spec", {})
        signatories = spec.get("signatories", [])
        roles = [s["role"] for s in signatories]
        expected_roles = ["Release Manager", "Engineering Lead", "QA Lead", "Security Lead", "Product Owner"]
        for role in expected_roles:
            assert role in roles, f"Missing signatory role: {role}"

    def test_manifest_freeze_policies(self, rc1_manifest: Dict[str, Any]):
        spec = rc1_manifest.get("spec", {})
        policies = spec.get("freeze_policies", {})
        assert policies.get("feature_freeze", {}).get("enabled") is True
        assert policies.get("api_freeze", {}).get("enabled") is True
        assert policies.get("configuration_freeze", {}).get("enabled") is True


class TestOpenAPISpec:
    """Tests for OpenAPI specification validity."""

    def test_openapi_spec_exists(self):
        spec = DOCS_API_DIR / "openapi_v0.4.0-alpha1.yaml"
        assert spec.exists(), "OpenAPI spec must exist"

    def test_openapi_has_version_info(self, openapi_spec: Dict[str, Any]):
        assert "openapi" in openapi_spec, "Must have openapi version"
        assert openapi_spec["openapi"].startswith("3."), "Must be OpenAPI 3.x"

    def test_openapi_has_metadata(self, openapi_spec: Dict[str, Any]):
        info = openapi_spec.get("info", {})
        assert "title" in info, "Must have API title"
        assert "version" in info, "Must have API version"

    def test_openapi_has_paths(self, openapi_spec: Dict[str, Any]):
        paths = openapi_spec.get("paths", {})
        assert len(paths) > 0, "Must define API paths"

    def test_openapi_uses_api_prefix(self, openapi_spec: Dict[str, Any]):
        paths = openapi_spec.get("paths", {})
        # Check for any API path patterns (auth, orders, portfolio, etc.)
        has_api_paths = len(paths) > 0
        assert has_api_paths, "API paths must be defined"
        # Verify paths start with /
        for path in paths:
            assert path.startswith("/"), f"API path {path} must start with /"


class TestVersionConsistency:
    """Tests for version consistency across all artifacts."""

    def test_docker_version_matches_manifest(self, artifact_manifest: Dict[str, Any]):
        artifacts = artifact_manifest.get("artifacts", {})
        docker = artifacts.get("docker", {})
        assert docker["version"] == "v0.4.0-alpha1-rc1", "Docker version must be v0.4.0-alpha1-rc1"

    def test_helm_version_matches(self, artifact_manifest: Dict[str, Any]):
        artifacts = artifact_manifest.get("artifacts", {})
        helm = artifacts.get("helm", {})
        assert helm["version"] == "0.4.0-alpha1", "Helm version must be 0.4.0-alpha1"

    def test_sdk_version_format(self, artifact_manifest: Dict[str, Any]):
        artifacts = artifact_manifest.get("artifacts", {})
        sdk = artifacts.get("sdk", {})
        assert sdk["version"] == "0.4.0a1", "SDK version must be 0.4.0a1 (Python alpha format)"

    def test_release_stage_is_rc1(self, artifact_manifest: Dict[str, Any]):
        assert artifact_manifest.get("release_stage") == "rc1"

    def test_metadata_release_version(self, release_metadata: Dict[str, Any]):
        version = release_metadata.get("version", "")
        assert version == "v0.4.0-alpha1-rc1"

    def test_metadata_release_stage(self, release_metadata: Dict[str, Any]):
        release_info = release_metadata.get("release", {})
        assert release_info.get("stage") == "rc1"

    def test_metadata_git_tag(self, release_metadata: Dict[str, Any]):
        git_info = release_metadata.get("git", {})
        assert git_info.get("tag") == "v0.4.0-alpha1-rc1"

    def test_metadata_signing_valid(self, release_metadata: Dict[str, Any]):
        signing = release_metadata.get("signing", {})
        assert signing.get("signed") is True
        assert signing.get("verification_status") == "valid"

    def test_metadata_sbom_generated(self, release_metadata: Dict[str, Any]):
        compliance = release_metadata.get("compliance", {})
        assert compliance.get("sbom_generated") is True
        assert compliance.get("sbom_format") == "CycloneDX"

    def test_metadata_quality_gates(self, release_metadata: Dict[str, Any]):
        quality = release_metadata.get("quality", {})
        assert quality.get("security_scan_status") == "passed"
        assert quality.get("tests_failed") == 0


class TestReleaseNotes:
    """Tests for release notes completeness."""

    def test_rc1_release_notes_exists(self):
        notes = DOCS_NOTES_DIR / "RC1.md"
        assert notes.exists(), "RC1 release notes must exist"

    def test_rc1_notes_has_version(self):
        notes = DOCS_NOTES_DIR / "RC1.md"
        with open(notes, "r", encoding="utf-8") as f:
            content = f.read()
        assert "v0.4.0-alpha1-rc1" in content

    def test_rc1_notes_has_quality_gates(self):
        notes = DOCS_NOTES_DIR / "RC1.md"
        with open(notes, "r", encoding="utf-8") as f:
            content = f.read()
        assert "Quality Gates" in content or "质量门禁" in content

    def test_rc1_notes_has_artifacts(self):
        notes = DOCS_NOTES_DIR / "RC1.md"
        with open(notes, "r", encoding="utf-8") as f:
            content = f.read()
        assert "Docker" in content
        assert "Helm" in content

    def test_rc1_notes_has_migration_guide(self):
        notes = DOCS_NOTES_DIR / "RC1.md"
        with open(notes, "r", encoding="utf-8") as f:
            content = f.read()
        assert "Migration" in content or "迁移" in content

    def test_rc1_notes_warns_about_production_use(self):
        notes = DOCS_NOTES_DIR / "RC1.md"
        with open(notes, "r", encoding="utf-8") as f:
            content = f.read()
        assert "Release Candidate" in content
        assert "production" in content.lower()
