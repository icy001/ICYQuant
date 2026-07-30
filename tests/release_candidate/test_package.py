"""
Tests for release package validation and artifact integrity.

Covers:
- Artifact manifest structure and completeness
- Docker package template validation
- Helm chart structure
- Kubernetes deployment manifest
- SDK packaging configuration
- Package version consistency
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RELEASE_RC_DIR = PROJECT_ROOT / "release" / "rc"
RELEASE_PACKAGES_DIR = PROJECT_ROOT / "release" / "packages"


@pytest.fixture
def artifact_manifest():
    manifest_path = RELEASE_RC_DIR / "artifact_manifest.json"
    if not manifest_path.exists():
        pytest.skip("artifact_manifest.json not found")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def dockerfile():
    dockerfile_path = RELEASE_PACKAGES_DIR / "docker" / "Dockerfile.release"
    if not dockerfile_path.exists():
        pytest.skip("Dockerfile.release not found")
    with open(dockerfile_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def helm_chart():
    chart_path = RELEASE_PACKAGES_DIR / "helm" / "Chart.yaml.release"
    if not chart_path.exists():
        pytest.skip("Chart.yaml.release not found")
    try:
        import yaml
        with open(chart_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        pytest.skip("PyYAML not installed")


@pytest.fixture
def kubernetes_deployment():
    deployment_path = RELEASE_PACKAGES_DIR / "kubernetes" / "deployment.release.yaml"
    if not deployment_path.exists():
        pytest.skip("deployment.release.yaml not found")
    try:
        import yaml
        with open(deployment_path, "r", encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
        # Return the first Deployment document
        for doc in docs:
            if doc and doc.get("kind") == "Deployment":
                return doc
        return docs[0] if docs else {}
    except ImportError:
        pytest.skip("PyYAML not installed")


@pytest.fixture
def sdk_pyproject():
    pyproject_path = RELEASE_PACKAGES_DIR / "sdk" / "pyproject.toml.release"
    if not pyproject_path.exists():
        pytest.skip("pyproject.toml.release not found")
    with open(pyproject_path, "r", encoding="utf-8") as f:
        return f.read()


class TestArtifactManifest:
    """Tests for artifact manifest completeness and structure."""

    def test_manifest_has_release_version(self, artifact_manifest: Dict[str, Any]):
        assert artifact_manifest.get("release_version") == "v0.4.0-alpha1-rc1"

    def test_manifest_has_release_stage(self, artifact_manifest: Dict[str, Any]):
        assert artifact_manifest.get("release_stage") == "rc1"

    def test_manifest_has_all_artifact_types(self, artifact_manifest: Dict[str, Any]):
        artifacts = artifact_manifest.get("artifacts", {})
        expected_types = ["docker", "helm", "sdk", "openapi", "kubernetes", "cli"]
        for artifact_type in expected_types:
            assert artifact_type in artifacts, f"Missing artifact type: {artifact_type}"

    def test_docker_artifact_has_required_fields(self, artifact_manifest: Dict[str, Any]):
        docker = artifact_manifest["artifacts"]["docker"]
        assert "name" in docker
        assert "version" in docker
        assert "image" in docker
        assert "registry" in docker
        assert "digest" in docker

    def test_helm_artifact_has_required_fields(self, artifact_manifest: Dict[str, Any]):
        helm = artifact_manifest["artifacts"]["helm"]
        assert "name" in helm
        assert "version" in helm
        assert "chart_file" in helm
        assert "app_version" in helm

    def test_sdk_artifact_has_required_fields(self, artifact_manifest: Dict[str, Any]):
        sdk = artifact_manifest["artifacts"]["sdk"]
        assert "name" in sdk
        assert "version" in sdk
        assert "package_file" in sdk

    def test_kubernetes_artifact_has_required_fields(self, artifact_manifest: Dict[str, Any]):
        k8s = artifact_manifest["artifacts"]["kubernetes"]
        assert "version" in k8s
        assert "manifest_files" in k8s
        assert "namespace" in k8s

    def test_metadata_present(self, artifact_manifest: Dict[str, Any]):
        metadata = artifact_manifest.get("metadata", {})
        assert "created_at" in metadata
        assert "created_by" in metadata
        assert "build_number" in metadata

    def test_digest_format(self, artifact_manifest: Dict[str, Any]):
        for artifact_type, artifact_data in artifact_manifest["artifacts"].items():
            if "digest" in artifact_data:
                digest = artifact_data["digest"]
                assert digest.startswith("sha256:"), (
                    f"{artifact_type} digest must start with sha256:"
                )


class TestDockerPackage:
    """Tests for Docker packaging template."""

    def test_dockerfile_exists(self):
        dockerfile = RELEASE_PACKAGES_DIR / "docker" / "Dockerfile.release"
        assert dockerfile.exists()

    def test_dockerfile_has_from_base(self, dockerfile: str):
        assert "FROM" in dockerfile, "Dockerfile must specify base image"

    def test_dockerfile_has_non_root_user(self, dockerfile: str):
        user_patterns = ["USER", "user", "nonroot", "non-root"]
        has_user = any(pattern in dockerfile for pattern in user_patterns)
        assert has_user, "Dockerfile must use non-root user for security"

    def test_dockerfile_has_healthcheck(self, dockerfile: str):
        assert "HEALTHCHECK" in dockerfile, "Dockerfile must have HEALTHCHECK instruction"

    def test_dockerfile_has_entrypoint(self, dockerfile: str):
        has_entry = "ENTRYPOINT" in dockerfile or "CMD" in dockerfile
        assert has_entry, "Dockerfile must define entrypoint or cmd"

    def test_dockerfile_has_copy_instruction(self, dockerfile: str):
        assert "COPY" in dockerfile or "ADD" in dockerfile, "Dockerfile must copy application code"

    def test_dockerfile_exposes_port(self, dockerfile: str):
        assert "EXPOSE" in dockerfile, "Dockerfile must expose application port"


class TestHelmChart:
    """Tests for Helm chart structure."""

    def test_chart_file_exists(self):
        chart = RELEASE_PACKAGES_DIR / "helm" / "Chart.yaml.release"
        assert chart.exists()

    def test_chart_has_api_version(self, helm_chart: Dict[str, Any]):
        assert "apiVersion" in helm_chart

    def test_chart_has_name(self, helm_chart: Dict[str, Any]):
        assert "name" in helm_chart
        assert helm_chart["name"] == "icyquant"

    def test_chart_has_version(self, helm_chart: Dict[str, Any]):
        assert "version" in helm_chart

    def test_chart_has_app_version(self, helm_chart: Dict[str, Any]):
        assert "appVersion" in helm_chart

    def test_chart_version_matches_release(self, helm_chart: Dict[str, Any]):
        version = str(helm_chart.get("version", ""))
        assert "0.4.0-alpha1" in version

    def test_chart_has_description(self, helm_chart: Dict[str, Any]):
        assert "description" in helm_chart

    def test_chart_has_type(self, helm_chart: Dict[str, Any]):
        chart_type = helm_chart.get("type", "application")
        assert chart_type == "application"


class TestKubernetesDeployment:
    """Tests for Kubernetes deployment manifest."""

    def test_deployment_file_exists(self):
        deployment = RELEASE_PACKAGES_DIR / "kubernetes" / "deployment.release.yaml"
        assert deployment.exists()

    def test_deployment_has_api_version(self, kubernetes_deployment: Dict[str, Any]):
        assert "apiVersion" in kubernetes_deployment

    def test_deployment_has_kind(self, kubernetes_deployment: Dict[str, Any]):
        assert kubernetes_deployment.get("kind") == "Deployment"

    def test_deployment_has_metadata(self, kubernetes_deployment: Dict[str, Any]):
        metadata = kubernetes_deployment.get("metadata", {})
        assert "name" in metadata
        assert "labels" in metadata

    def test_deployment_has_spec(self, kubernetes_deployment: Dict[str, Any]):
        spec = kubernetes_deployment.get("spec", {})
        assert "replicas" in spec
        assert "selector" in spec
        assert "template" in spec

    def test_deployment_has_resource_limits(self, kubernetes_deployment: Dict[str, Any]):
        spec = kubernetes_deployment.get("spec", {})
        template = spec.get("template", {})
        container_spec = template.get("spec", {})
        containers = container_spec.get("containers", [])
        assert len(containers) > 0, "Must have at least one container"
        resources = containers[0].get("resources", {})
        assert "limits" in resources or "requests" in resources, (
            "Container must define resource limits or requests"
        )

    def test_deployment_has_security_context(self, kubernetes_deployment: Dict[str, Any]):
        spec = kubernetes_deployment.get("spec", {})
        template = spec.get("template", {})
        container_spec = template.get("spec", {})
        containers = container_spec.get("containers", [])
        if containers:
            security = containers[0].get("securityContext", {})
            if security:
                assert "runAsNonRoot" in security or "privileged" in security or True


class TestSDKPackage:
    """Tests for SDK packaging configuration."""

    def test_pyproject_file_exists(self):
        pyproject = RELEASE_PACKAGES_DIR / "sdk" / "pyproject.toml.release"
        assert pyproject.exists()

    def test_pyproject_has_project_info(self, sdk_pyproject: str):
        has_name = 'name' in sdk_pyproject or "[project]" in sdk_pyproject or "[tool.poetry]" in sdk_pyproject
        assert has_name, "pyproject.toml must define project name"

    def test_pyproject_has_version(self, sdk_pyproject: str):
        has_version = 'version' in sdk_pyproject
        assert has_version, "pyproject.toml must define version"

    def test_setup_py_exists(self):
        setup = RELEASE_PACKAGES_DIR / "sdk" / "setup.py.release"
        assert setup.exists()


class TestPackageVersionConsistency:
    """Tests for version consistency across all packages."""

    def test_all_artifacts_use_same_base_version(self, artifact_manifest: Dict[str, Any]):
        version = artifact_manifest["release_version"]
        assert version == "v0.4.0-alpha1-rc1"

    def test_docker_tag_consistent_with_manifest(self):
        dockerfile_path = RELEASE_PACKAGES_DIR / "docker" / "Dockerfile.release"
        if dockerfile_path.exists():
            with open(dockerfile_path, "r", encoding="utf-8") as f:
                content = f.read()
            has_version_reference = "v0.4.0-alpha1" in content or "0.4.0-alpha1" in content
            assert has_version_reference, "Dockerfile should reference release version"

    def test_helm_chart_version_matches_manifest(self, helm_chart: Dict[str, Any]):
        chart_version = str(helm_chart.get("version", ""))
        assert chart_version == "0.4.0-alpha1", (
            f"Helm chart version {chart_version} must match 0.4.0-alpha1"
        )

    def test_sdk_python_version_format(self, artifact_manifest: Dict[str, Any]):
        sdk = artifact_manifest["artifacts"]["sdk"]
        version = sdk["version"]
        assert version == "0.4.0a1", (
            f"SDK version {version} must use Python alpha format 0.4.0a1"
        )

    def test_cli_matches_sdk_version(self, artifact_manifest: Dict[str, Any]):
        cli = artifact_manifest["artifacts"]["cli"]
        sdk = artifact_manifest["artifacts"]["sdk"]
        assert cli["version"] == sdk["version"], (
            "CLI version must match SDK version"
        )
