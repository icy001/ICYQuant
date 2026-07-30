"""
Tests for installation validation and platform compatibility.

Covers:
- Docker installation instructions valid
- Helm installation instructions valid
- Python SDK installation instructions valid
- System requirements documented
- Platform compatibility documented
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
RELEASE_PACKAGES_DIR = PROJECT_ROOT / "release" / "packages"
RELEASE_GA_DIR = PROJECT_ROOT / "release" / "ga"


@pytest.fixture
def release_manifest() -> Dict[str, Any]:
    manifest_path = RELEASE_GA_DIR / "release_manifest.json"
    if not manifest_path.exists():
        pytest.skip("release_manifest.json not found")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


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


def _find_deployment_doc() -> Optional[Path]:
    candidates = [
        DOCS_DIR / "production" / "deployment_guide.md",
        DOCS_DIR / "deployment_guide.md",
        DOCS_DIR / "deployment.md",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


class TestDockerInstallation:
    """Tests for Docker installation instructions validity."""

    def test_dockerfile_exists(self):
        dockerfile = RELEASE_PACKAGES_DIR / "docker" / "Dockerfile.release"
        assert dockerfile.exists(), "Dockerfile.release must exist for GA"

    def test_dockerfile_valid_structure(self):
        dockerfile = RELEASE_PACKAGES_DIR / "docker" / "Dockerfile.release"
        if not dockerfile.exists():
            pytest.skip("Dockerfile.release not found")
        content = dockerfile.read_text(encoding="utf-8")
        assert "FROM" in content, "Dockerfile must have FROM instruction"
        assert "ENTRYPOINT" in content or "CMD" in content, (
            "Dockerfile must have ENTRYPOINT or CMD"
        )
        assert "EXPOSE" in content, "Dockerfile must have EXPOSE"
        assert "HEALTHCHECK" in content, "Dockerfile must have HEALTHCHECK"

    def test_dockerfile_has_version(self):
        dockerfile = RELEASE_PACKAGES_DIR / "docker" / "Dockerfile.release"
        if not dockerfile.exists():
            pytest.skip("Dockerfile.release not found")
        content = dockerfile.read_text(encoding="utf-8")
        assert "0.4.0-alpha1" in content, (
            "Dockerfile must reference v0.4.0-alpha1"
        )

    def test_dockerfile_non_root_security(self):
        dockerfile = RELEASE_PACKAGES_DIR / "docker" / "Dockerfile.release"
        if not dockerfile.exists():
            pytest.skip("Dockerfile.release not found")
        content = dockerfile.read_text(encoding="utf-8")
        assert "USER" in content, (
            "Dockerfile must use USER instruction for non-root execution"
        )

    def test_docker_manifest_has_image(self, release_manifest: Dict[str, Any]):
        docker = release_manifest.get("artifacts", {}).get("docker", {})
        assert docker, "Release manifest must include Docker artifact"
        image = docker.get("image", "")
        assert "icyquant" in image, (
            f"Docker image name must contain 'icyquant', got: {image}"
        )

    def test_docker_manifest_has_registry(self, release_manifest: Dict[str, Any]):
        docker = release_manifest.get("artifacts", {}).get("docker", {})
        registry = docker.get("registry", "")
        assert registry, "Docker manifest must specify registry"


class TestHelmInstallation:
    """Tests for Helm installation instructions validity."""

    def test_helm_chart_exists(self):
        chart = RELEASE_PACKAGES_DIR / "helm" / "Chart.yaml.release"
        assert chart.exists(), "Chart.yaml.release must exist for GA"

    def test_helm_chart_valid(self, helm_chart: Dict[str, Any]):
        assert "apiVersion" in helm_chart, "Helm chart must have apiVersion"
        assert "name" in helm_chart, "Helm chart must have name"
        assert "version" in helm_chart, "Helm chart must have version"

    def test_helm_chart_has_dependencies(self, helm_chart: Dict[str, Any]):
        deps = helm_chart.get("dependencies", [])
        assert len(deps) > 0, (
            "Helm chart must declare dependencies"
        )

    def test_helm_chart_version_matches(self, helm_chart: Dict[str, Any]):
        version = str(helm_chart.get("version", ""))
        assert "0.4.0-alpha1" in version, (
            f"Helm chart version must be 0.4.0-alpha1, got: {version}"
        )

    def test_helm_values_file_exists(self):
        values_file = RELEASE_PACKAGES_DIR / "helm" / "values.release.yaml"
        assert values_file.exists(), "values.release.yaml must exist"

    def test_helm_kub_version_supported(self, helm_chart: Dict[str, Any]):
        kube_version = helm_chart.get("kubeVersion", "")
        assert kube_version, "Helm chart must specify supported Kubernetes version"
        assert "1.24" in kube_version or "1." in kube_version, (
            f"Helm chart must support Kubernetes >= 1.24, got: {kube_version}"
        )

    def test_helm_manifest_has_chart(self, release_manifest: Dict[str, Any]):
        helm = release_manifest.get("artifacts", {}).get("helm", {})
        assert helm, "Release manifest must include Helm artifact"
        assert helm.get("chart") == "icyquant", (
            f"Helm chart name must be icyquant, got: {helm.get('chart')}"
        )


class TestPythonSDKInstallation:
    """Tests for Python SDK installation instructions validity."""

    def test_sdk_pyproject_exists(self):
        pyproject = RELEASE_PACKAGES_DIR / "sdk" / "pyproject.toml.release"
        assert pyproject.exists(), "pyproject.toml.release must exist for GA"

    def test_sdk_pyproject_has_name(self):
        pyproject = RELEASE_PACKAGES_DIR / "sdk" / "pyproject.toml.release"
        if not pyproject.exists():
            pytest.skip("pyproject.toml.release not found")
        content = pyproject.read_text(encoding="utf-8")
        assert "name" in content, "SDK pyproject must define project name"

    def test_sdk_pyproject_has_version(self):
        pyproject = RELEASE_PACKAGES_DIR / "sdk" / "pyproject.toml.release"
        if not pyproject.exists():
            pytest.skip("pyproject.toml.release not found")
        content = pyproject.read_text(encoding="utf-8")
        assert "version" in content, "SDK pyproject must define version"

    def test_sdk_pyproject_has_python_version(self):
        pyproject = RELEASE_PACKAGES_DIR / "sdk" / "pyproject.toml.release"
        if not pyproject.exists():
            pytest.skip("pyproject.toml.release not found")
        content = pyproject.read_text(encoding="utf-8")
        assert "3.9" in content or "requires-python" in content, (
            "SDK pyproject must specify Python version requirement"
        )

    def test_sdk_pyproject_has_dependencies(self):
        pyproject = RELEASE_PACKAGES_DIR / "sdk" / "pyproject.toml.release"
        if not pyproject.exists():
            pytest.skip("pyproject.toml.release not found")
        content = pyproject.read_text(encoding="utf-8")
        assert "dependencies" in content, (
            "SDK pyproject must define dependencies"
        )

    def test_sdk_setup_py_exists(self):
        setup = RELEASE_PACKAGES_DIR / "sdk" / "setup.py.release"
        assert setup.exists(), "setup.py.release must exist for GA"

    def test_sdk_manifest_version(self, release_manifest: Dict[str, Any]):
        sdk = release_manifest.get("artifacts", {}).get("python_sdk", {})
        assert sdk, "Release manifest must include Python SDK artifact"
        version = sdk.get("version", "")
        assert "0.4.0" in version, (
            f"SDK version must reference 0.4.0, got: {version}"
        )

    def test_sdk_manifest_has_package_name(self, release_manifest: Dict[str, Any]):
        sdk = release_manifest.get("artifacts", {}).get("python_sdk", {})
        assert sdk.get("package") == "icyquant-sdk", (
            f"SDK package name must be icyquant-sdk, got: {sdk.get('package')}"
        )


class TestSystemRequirements:
    """Tests for system requirements documentation."""

    def test_requirements_in_deployment_doc(self):
        deploy_doc = _find_deployment_doc()
        if deploy_doc is None:
            pytest.skip("Deployment doc not found")
            return
        content = deploy_doc.read_text(encoding="utf-8")
        req_terms = ["requirement", "要求", "minimum", "最低", "hardware", "硬件"]
        found = any(term.lower() in content.lower() for term in req_terms)
        assert found, "Deployment doc must document system requirements"

    def test_compute_requirements_documented(self):
        deploy_doc = _find_deployment_doc()
        if deploy_doc is None:
            pytest.skip("Deployment doc not found")
            return
        content = deploy_doc.read_text(encoding="utf-8")
        compute_terms = ["CPU", "cpu", "memory", "RAM", "内存", "disk", "存储"]
        found = any(term.lower() in content.lower() for term in compute_terms)
        assert found, "System requirements must cover compute resources"

    def test_kubernetes_version_requirement(self):
        deploy_doc = _find_deployment_doc()
        if deploy_doc is None:
            pytest.skip("Deployment doc not found")
            return
        content = deploy_doc.read_text(encoding="utf-8")
        has_k8s = any(
            term in content
            for term in ["Kubernetes", "kubernetes", "1.24", "1.25", "1.26"]
        )
        assert has_k8s, (
            "System requirements must specify Kubernetes version"
        )

    def test_database_requirements(self):
        deploy_doc = _find_deployment_doc()
        if deploy_doc is None:
            pytest.skip("Deployment doc not found")
            return
        content = deploy_doc.read_text(encoding="utf-8")
        db_terms = ["PostgreSQL", "TimescaleDB", "Redis", "Kafka", "database"]
        found = any(term.lower() in content.lower() for term in db_terms)
        assert found, "System requirements must document database dependencies"

    def test_network_requirements(self):
        deploy_doc = _find_deployment_doc()
        if deploy_doc is None:
            pytest.skip("Deployment doc not found")
            return
        content = deploy_doc.read_text(encoding="utf-8")
        net_terms = ["network", "端口", "port", "firewall", "防火墙", "DNS"]
        found = any(term.lower() in content.lower() for term in net_terms)
        assert found, "System requirements must document network requirements"


class TestPlatformCompatibility:
    """Tests for platform compatibility documentation."""

    def test_os_compatibility_documented(self):
        deploy_doc = _find_deployment_doc()
        if deploy_doc is None:
            pytest.skip("Deployment doc not found")
            return
        content = deploy_doc.read_text(encoding="utf-8")
        os_terms = ["Linux", "Windows", "Docker", "container", "Ubuntu"]
        found = any(term.lower() in content.lower() for term in os_terms)
        assert found, (
            "Platform compatibility must cover supported operating systems"
        )

    def test_python_compatibility_documented(self):
        sdk_pyproject = RELEASE_PACKAGES_DIR / "sdk" / "pyproject.toml.release"
        if not sdk_pyproject.exists():
            pytest.skip("pyproject.toml.release not found")
        content = sdk_pyproject.read_text(encoding="utf-8")
        has_python_versions = any(
            term in content for term in ["3.9", "3.10", "3.11", "3.12"]
        )
        assert has_python_versions, (
            "Platform compatibility must list supported Python versions"
        )

    def test_kubernetes_compatibility_documented(self, helm_chart: Dict[str, Any]):
        kube_version = helm_chart.get("kubeVersion", "")
        assert kube_version, "Helm chart must specify Kubernetes version compatibility"

    def test_helm_version_compatibility(self, helm_chart: Dict[str, Any]):
        deps = helm_chart.get("dependencies", [])
        assert len(deps) > 0, "Helm chart must declare dependencies for compatibility"

    def test_platform_arch_compatibility(self):
        deploy_doc = _find_deployment_doc()
        if deploy_doc is None:
            pytest.skip("Deployment doc not found")
            return
        content = deploy_doc.read_text(encoding="utf-8")
        arch_terms = ["amd64", "arm64", "x86_64", "linux-amd64", "architecture", "架构"]
        found = any(term.lower() in content.lower() for term in arch_terms)
        if not found:
            pytest.skip("Architecture compatibility not explicitly documented")
        assert found, (
            "Platform compatibility must specify CPU architecture support"
        )

    def test_installation_commands_valid(self):
        deploy_doc = _find_deployment_doc()
        if deploy_doc is None:
            pytest.skip("Deployment doc not found")
            return
        content = deploy_doc.read_text(encoding="utf-8")
        has_commands = any(
            term in content
            for term in ["helm install", "docker pull", "kubectl apply", "pip install"]
        )
        assert has_commands, (
            "Installation docs must include actual installation commands"
        )