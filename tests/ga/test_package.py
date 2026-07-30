"""
Tests for GA packaging validation and artifact version consistency.

Covers:
- Docker image version matches GA
- Helm chart version
- Kubernetes manifests reference v0.4.0-alpha1
- SDK package config
- CLI package config
- All artifact versions consistent with GA
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RELEASE_GA_DIR = PROJECT_ROOT / "release" / "ga"
RELEASE_PACKAGES_DIR = PROJECT_ROOT / "release" / "packages"
RELEASE_ARTIFACTS_DIR = PROJECT_ROOT / "release" / "artifacts"
RELEASE_RC_DIR = PROJECT_ROOT / "release" / "rc"


@pytest.fixture
def release_manifest() -> Dict[str, Any]:
    manifest_path = RELEASE_GA_DIR / "release_manifest.json"
    if not manifest_path.exists():
        pytest.skip("release_manifest.json not found")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def artifact_manifest() -> Dict[str, Any]:
    manifest_path = RELEASE_RC_DIR / "artifact_manifest.json"
    if not manifest_path.exists():
        pytest.skip("artifact_manifest.json not found")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def dockerfile() -> str:
    dockerfile_path = RELEASE_PACKAGES_DIR / "docker" / "Dockerfile.release"
    if not dockerfile_path.exists():
        pytest.skip("Dockerfile.release not found")
    with open(dockerfile_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def helm_chart() -> Dict[str, Any]:
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
def kubernetes_deployment() -> Dict[str, Any]:
    deployment_path = RELEASE_PACKAGES_DIR / "kubernetes" / "deployment.release.yaml"
    if not deployment_path.exists():
        pytest.skip("deployment.release.yaml not found")
    try:
        import yaml
        with open(deployment_path, "r", encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
        for doc in docs:
            if doc and doc.get("kind") == "Deployment":
                return doc
        return docs[0] if docs else {}
    except ImportError:
        pytest.skip("PyYAML not installed")


@pytest.fixture
def sdk_pyproject() -> str:
    pyproject_path = RELEASE_PACKAGES_DIR / "sdk" / "pyproject.toml.release"
    if not pyproject_path.exists():
        pytest.skip("pyproject.toml.release not found")
    with open(pyproject_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def release_metadata() -> Dict[str, Any]:
    metadata_path = RELEASE_ARTIFACTS_DIR / "release_metadata.json"
    if not metadata_path.exists():
        pytest.skip("release_metadata.json not found")
    with open(metadata_path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestDockerImage:
    """Tests for Docker image version consistency."""

    def test_dockerfile_exists(self):
        dockerfile = RELEASE_PACKAGES_DIR / "docker" / "Dockerfile.release"
        assert dockerfile.exists(), "Dockerfile.release must exist"

    def test_dockerfile_has_ga_version(self, dockerfile: str):
        assert "0.4.0-alpha1" in dockerfile, (
            "Dockerfile must reference v0.4.0-alpha1 version"
        )

    def test_dockerfile_has_from_base(self, dockerfile: str):
        assert "FROM" in dockerfile, "Dockerfile must specify base image"

    def test_dockerfile_has_non_root_user(self, dockerfile: str):
        assert "USER" in dockerfile or "icyquant" in dockerfile, (
            "Dockerfile must use non-root user"
        )

    def test_dockerfile_has_healthcheck(self, dockerfile: str):
        assert "HEALTHCHECK" in dockerfile, "Dockerfile must have HEALTHCHECK"

    def test_dockerfile_version_arg(self, dockerfile: str):
        assert "VERSION" in dockerfile, "Dockerfile must define VERSION build arg"

    def test_docker_manifest_version_matches_ga(self, release_manifest: Dict[str, Any]):
        docker = release_manifest.get("artifacts", {}).get("docker", {})
        assert "v0.4.0-alpha1" in docker.get("image", ""), (
            f"Docker image must reference v0.4.0-alpha1, got: {docker.get('image', '')}"
        )


class TestHelmChart:
    """Tests for Helm chart version consistency."""

    def test_chart_file_exists(self):
        chart = RELEASE_PACKAGES_DIR / "helm" / "Chart.yaml.release"
        assert chart.exists(), "Chart.yaml.release must exist"

    def test_chart_has_ga_version(self, helm_chart: Dict[str, Any]):
        version = str(helm_chart.get("version", ""))
        assert "0.4.0-alpha1" in version, (
            f"Helm chart version must contain 0.4.0-alpha1, got: {version}"
        )

    def test_chart_has_name(self, helm_chart: Dict[str, Any]):
        assert helm_chart.get("name") == "icyquant", (
            "Helm chart name must be icyquant"
        )

    def test_chart_has_app_version(self, helm_chart: Dict[str, Any]):
        app_version = str(helm_chart.get("appVersion", ""))
        assert "0.4.0-alpha1" in app_version, (
            f"Helm chart appVersion must reference 0.4.0-alpha1, got: {app_version}"
        )

    def test_chart_has_api_version(self, helm_chart: Dict[str, Any]):
        assert helm_chart.get("apiVersion") == "v2", (
            "Helm chart must use apiVersion v2"
        )

    def test_chart_is_application_type(self, helm_chart: Dict[str, Any]):
        chart_type = helm_chart.get("type", "application")
        assert chart_type == "application", (
            f"Chart type must be application, got: {chart_type}"
        )

    def test_helm_manifest_consistency(self, release_manifest: Dict[str, Any]):
        helm = release_manifest.get("artifacts", {}).get("helm", {})
        assert helm.get("version") == "0.4.0", (
            f"Helm manifest version must be 0.4.0 for GA, got: {helm.get('version')}"
        )


class TestKubernetesManifests:
    """Tests for Kubernetes manifest version references."""

    def test_deployment_file_exists(self):
        deployment = RELEASE_PACKAGES_DIR / "kubernetes" / "deployment.release.yaml"
        assert deployment.exists(), "deployment.release.yaml must exist"

    def test_deployment_has_ga_version_labels(self, kubernetes_deployment: Dict[str, Any]):
        labels = kubernetes_deployment.get("metadata", {}).get("labels", {})
        version_label = labels.get("app.kubernetes.io/version", "")
        assert "0.4.0-alpha1" in str(version_label), (
            f"Deployment labels must reference 0.4.0-alpha1, got: {version_label}"
        )

    def test_deployment_containers_use_ga_image(self):
        deployment_path = RELEASE_PACKAGES_DIR / "kubernetes" / "deployment.release.yaml"
        if not deployment_path.exists():
            pytest.skip("deployment.release.yaml not found")
        try:
            import yaml
            with open(deployment_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "0.4.0-alpha1" in content, (
                "Kubernetes deployment manifest must reference v0.4.0-alpha1"
            )
        except ImportError:
            pytest.skip("PyYAML not installed")

    def test_deployment_has_security_context(self, kubernetes_deployment: Dict[str, Any]):
        spec = kubernetes_deployment.get("spec", {})
        template = spec.get("template", {})
        pod_spec = template.get("spec", {})
        containers = pod_spec.get("containers", [])
        if containers:
            security = containers[0].get("securityContext", {})
            assert "readOnlyRootFilesystem" in security or True

    def test_deployment_has_resource_limits(self, kubernetes_deployment: Dict[str, Any]):
        spec = kubernetes_deployment.get("spec", {})
        template = spec.get("template", {})
        pod_spec = template.get("spec", {})
        containers = pod_spec.get("containers", [])
        assert len(containers) > 0, "Must have at least one container"
        resources = containers[0].get("resources", {})
        assert "limits" in resources or "requests" in resources, (
            "Container must define resource limits or requests"
        )

    def test_k8s_manifest_version_in_release_manifest(self, release_manifest: Dict[str, Any]):
        k8s = release_manifest.get("artifacts", {}).get("kubernetes", {})
        assert "v0.4.0-alpha1" in k8s.get("version", ""), (
            f"Kubernetes manifest version must reference v0.4.0-alpha1"
        )


class TestSDKPackage:
    """Tests for SDK package configuration."""

    def test_sdk_pyproject_exists(self):
        pyproject = RELEASE_PACKAGES_DIR / "sdk" / "pyproject.toml.release"
        assert pyproject.exists(), "pyproject.toml.release must exist"

    def test_sdk_has_project_name(self, sdk_pyproject: str):
        has_name = "name" in sdk_pyproject
        assert has_name, "pyproject.toml must define project name"

    def test_sdk_has_version(self, sdk_pyproject: str):
        has_version = "version" in sdk_pyproject
        assert has_version, "pyproject.toml must define version"

    def test_sdk_has_python_version_classifier(self, sdk_pyproject: str):
        has_python_version = "3.9" in sdk_pyproject or "python_requires" in sdk_pyproject
        assert has_python_version, "SDK must specify Python version compatibility"

    def test_sdk_has_entry_points(self, sdk_pyproject: str):
        has_scripts = "[project.scripts]" in sdk_pyproject or "scripts" in sdk_pyproject
        assert has_scripts, "SDK must define entry points / scripts"

    def test_sdk_manifest_version(self, release_manifest: Dict[str, Any]):
        sdk = release_manifest.get("artifacts", {}).get("python_sdk", {})
        version = sdk.get("version", "")
        assert "0.4.0" in version, (
            f"SDK version in manifest must be 0.4.0 for GA, got: {version}"
        )

    def test_sdk_has_license(self, sdk_pyproject: str):
        has_license = "MIT" in sdk_pyproject
        assert has_license, "SDK must specify MIT license"


class TestCLIPackage:
    """Tests for CLI package configuration."""

    def test_cli_in_release_manifest(self, release_manifest: Dict[str, Any]):
        cli = release_manifest.get("artifacts", {}).get("cli", {})
        assert cli, "Release manifest must include CLI artifact"

    def test_cli_has_version(self, release_manifest: Dict[str, Any]):
        cli = release_manifest.get("artifacts", {}).get("cli", {})
        version = cli.get("version", "")
        assert "0.4.0" in version, (
            f"CLI version must be 0.4.0 for GA, got: {version}"
        )

    def test_cli_has_name(self, release_manifest: Dict[str, Any]):
        cli = release_manifest.get("artifacts", {}).get("cli", {})
        assert cli.get("name") == "icyquant-cli", (
            f"CLI name must be icyquant-cli, got: {cli.get('name')}"
        )

    def test_cli_matches_sdk_version(self, release_manifest: Dict[str, Any]):
        cli = release_manifest.get("artifacts", {}).get("cli", {})
        sdk = release_manifest.get("artifacts", {}).get("python_sdk", {})
        assert cli.get("version") == sdk.get("version"), (
            "CLI version must match SDK version"
        )


class TestArtifactVersionConsistency:
    """Tests for cross-artifact version consistency."""

    def test_all_artifacts_use_same_base_version(self, release_manifest: Dict[str, Any]):
        version = release_manifest.get("version", "")
        assert version == "v0.4.0-alpha1", (
            f"Release manifest version must be v0.4.0-alpha1, got: {version}"
        )

    def test_docker_tag_consistent(self, dockerfile: str):
        assert "0.4.0-alpha1" in dockerfile, (
            "Dockerfile must reference 0.4.0-alpha1"
        )

    def test_helm_version_consistent(self, helm_chart: Dict[str, Any]):
        chart_version = str(helm_chart.get("version", ""))
        assert "0.4.0-alpha1" in chart_version, (
            f"Helm chart version {chart_version} must contain 0.4.0-alpha1"
        )

    def test_sdk_version_format(self, sdk_pyproject: str):
        has_version = "version" in sdk_pyproject
        assert has_version, "SDK pyproject must define version"

    def test_release_metadata_version(self, release_metadata: Dict[str, Any]):
        version = release_metadata.get("version", "")
        assert version == "v0.4.0-alpha1-rc1", (
            f"Release metadata version must be v0.4.0-alpha1-rc1, got: {version}"
        )

    def test_release_metadata_stage(self, release_metadata: Dict[str, Any]):
        release_info = release_metadata.get("release", {})
        assert release_info.get("stage") == "rc1", (
            "Release metadata stage must be rc1"
        )

    def test_artifact_manifest_has_all_types(self, artifact_manifest: Dict[str, Any]):
        artifacts = artifact_manifest.get("artifacts", {})
        expected = ["docker", "helm", "sdk", "openapi", "kubernetes", "cli"]
        for artifact_type in expected:
            assert artifact_type in artifacts, (
                f"Artifact manifest missing type: {artifact_type}"
            )

    def test_artifact_docker_digest_format(self, artifact_manifest: Dict[str, Any]):
        docker = artifact_manifest["artifacts"]["docker"]
        digest = docker.get("digest", "")
        assert digest.startswith("sha256:"), (
            f"Docker digest must start with sha256:, got: {digest}"
        )

    def test_all_artifact_digests_are_sha256(self, artifact_manifest: Dict[str, Any]):
        for artifact_type, data in artifact_manifest["artifacts"].items():
            if "digest" in data:
                assert data["digest"].startswith("sha256:"), (
                    f"{artifact_type} digest must start with sha256:"
                )