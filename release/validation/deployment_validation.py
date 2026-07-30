"""
Deployment validation for the ICYQuant production system.

Validates deployment readiness including Kubernetes manifests,
Docker image builds, Helm charts, GitOps configuration, network
policies, resource limits, and health probes.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class DeploymentCheck:
    check_name: str
    passed: bool
    duration_ms: float
    remediation: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeploymentResult:
    overall_passed: bool
    total_duration_ms: float
    checks: list[DeploymentCheck] = field(default_factory=list)
    remediation_suggestions: list[str] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""

    @property
    def pass_rate(self) -> float:
        if not self.checks:
            return 0.0
        passed = sum(1 for c in self.checks if c.passed)
        return passed / len(self.checks)

    @property
    def failed_checks(self) -> list[DeploymentCheck]:
        return [c for c in self.checks if not c.passed]


class DeploymentValidator:
    """
    Validates deployment readiness for ICYQuant.

    Checks Kubernetes manifests validity, Docker image builds,
    Helm chart integrity, GitOps configuration, network policies,
    resource limits, and health probes.
    """

    def __init__(self, project_root: Optional[str] = None) -> None:
        self.project_root = project_root or os.getcwd()
        self._checks: list[tuple[str, Callable[[], DeploymentCheck]]] = []
        self._register_default_checks()

    def _register_default_checks(self) -> None:
        self._checks = [
            ("Kubernetes Manifests", self._check_kubernetes_manifests),
            ("Docker Image Build", self._check_docker_build),
            ("Helm Chart Integrity", self._check_helm_chart),
            ("GitOps Configuration", self._check_gitops_config),
            ("Network Policies", self._check_network_policies),
            ("Resource Limits", self._check_resource_limits),
            ("Health Probes", self._check_health_probes),
        ]

    def run(self) -> DeploymentResult:
        import datetime

        started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        overall_start = time.perf_counter()

        check_results: list[DeploymentCheck] = []
        remediation: list[str] = []

        for check_name, check_func in self._checks:
            try:
                result = check_func()
                check_results.append(result)
                if not result.passed and result.remediation:
                    remediation.append(result.remediation)
            except Exception as e:
                check_results.append(DeploymentCheck(
                    check_name=check_name,
                    passed=False,
                    duration_ms=0.0,
                    remediation=f"Exception during check: {e}",
                    details={"error": str(e)},
                ))

        overall_duration = (time.perf_counter() - overall_start) * 1000
        completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        overall_passed = all(c.passed for c in check_results)

        return DeploymentResult(
            overall_passed=overall_passed,
            total_duration_ms=overall_duration,
            checks=check_results,
            remediation_suggestions=remediation,
            started_at=started_at,
            completed_at=completed_at,
        )

    def _check_kubernetes_manifests(self) -> DeploymentCheck:
        start = time.perf_counter()
        manifests_dir = os.path.join(self.project_root, "deployment")
        if not os.path.isdir(manifests_dir):
            return DeploymentCheck(
                check_name="Kubernetes Manifests",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                remediation="Create deployment/ directory with Kubernetes manifests",
                details={"path": manifests_dir, "exists": False},
            )

        yaml_files = self._find_yaml_files(manifests_dir)
        if not yaml_files:
            return DeploymentCheck(
                check_name="Kubernetes Manifests",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                remediation="Add Kubernetes manifest YAML files to deployment/",
                details={"path": manifests_dir, "files_found": 0},
            )

        import yaml

        invalid_files: list[str] = []
        valid_count = 0
        for f in yaml_files:
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
                if isinstance(data, dict) and "kind" in data:
                    valid_count += 1
                elif isinstance(data, list):
                    valid_count += 1
                else:
                    invalid_files.append(f)
            except Exception as e:
                invalid_files.append(f"{f}: {e}")

        passed = len(invalid_files) == 0
        return DeploymentCheck(
            check_name="Kubernetes Manifests",
            passed=passed,
            duration_ms=(time.perf_counter() - start) * 1000,
            remediation="" if passed else f"Fix {len(invalid_files)} invalid manifest(s)",
            details={
                "files_found": len(yaml_files),
                "valid_count": valid_count,
                "invalid_files": invalid_files,
            },
        )

    def _check_docker_build(self) -> DeploymentCheck:
        start = time.perf_counter()
        dockerfile_path = os.path.join(self.project_root, "Dockerfile")
        compose_path = os.path.join(self.project_root, "docker-compose.yml")

        details: dict[str, Any] = {
            "dockerfile_exists": os.path.isfile(dockerfile_path),
            "compose_exists": os.path.isfile(compose_path),
        }

        if not details["dockerfile_exists"]:
            return DeploymentCheck(
                check_name="Docker Image Build",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                remediation="Create Dockerfile for the application",
                details=details,
            )

        try:
            with open(dockerfile_path, "r", encoding="utf-8") as f:
                content = f.read()

            if "FROM" not in content:
                return DeploymentCheck(
                    check_name="Docker Image Build",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    remediation="Dockerfile must contain a FROM instruction",
                    details=details,
                )

            if "CMD" not in content and "ENTRYPOINT" not in content:
                return DeploymentCheck(
                    check_name="Docker Image Build",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    remediation="Dockerfile must have CMD or ENTRYPOINT instruction",
                    details=details,
                )

            has_workdir = "WORKDIR" in content
            has_copy = "COPY" in content
            details["has_workdir"] = has_workdir
            details["has_copy"] = has_copy

            if details["compose_exists"]:
                import yaml
                with open(compose_path, "r", encoding="utf-8") as f:
                    compose_data = yaml.safe_load(f)
                if isinstance(compose_data, dict) and "services" in compose_data:
                    service_count = len(compose_data["services"])
                    details["compose_services"] = service_count

            return DeploymentCheck(
                check_name="Docker Image Build",
                passed=True,
                duration_ms=(time.perf_counter() - start) * 1000,
                details=details,
            )
        except Exception as e:
            return DeploymentCheck(
                check_name="Docker Image Build",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                remediation=f"Error analyzing Dockerfile: {e}",
                details=details,
            )

    def _check_helm_chart(self) -> DeploymentCheck:
        start = time.perf_counter()
        chart_path = os.path.join(self.project_root, "deployment", "helm", "Chart.yaml")

        if not os.path.isfile(chart_path):
            return DeploymentCheck(
                check_name="Helm Chart Integrity",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                remediation="Create Helm chart at deployment/helm/Chart.yaml",
                details={"path": chart_path, "exists": False},
            )

        values_path = os.path.join(self.project_root, "deployment", "helm", "values.yaml")
        if not os.path.isfile(values_path):
            return DeploymentCheck(
                check_name="Helm Chart Integrity",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                remediation="Create values.yaml alongside Chart.yaml",
                details={"chart_path": chart_path, "values_path": values_path, "values_exists": False},
            )

        try:
            import yaml
            with open(chart_path, "r", encoding="utf-8") as f:
                chart = yaml.safe_load(f)

            required_fields = ["apiVersion", "name", "version", "appVersion"]
            missing = [field for field in required_fields if field not in chart]
            if missing:
                return DeploymentCheck(
                    check_name="Helm Chart Integrity",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    remediation=f"Chart.yaml missing required fields: {missing}",
                    details={"missing_fields": missing},
                )

            if chart.get("apiVersion") != "v2":
                return DeploymentCheck(
                    check_name="Helm Chart Integrity",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    remediation="Chart.yaml apiVersion must be 'v2'",
                    details={"apiVersion": chart.get("apiVersion")},
                )

            with open(values_path, "r", encoding="utf-8") as f:
                values = yaml.safe_load(f)

            details: dict[str, Any] = {
                "chart_name": chart.get("name"),
                "chart_version": chart.get("version"),
                "app_version": chart.get("appVersion"),
                "has_values": True,
                "global_environment": values.get("global", {}).get("environment", "unknown"),
            }

            return DeploymentCheck(
                check_name="Helm Chart Integrity",
                passed=True,
                duration_ms=(time.perf_counter() - start) * 1000,
                details=details,
            )
        except Exception as e:
            return DeploymentCheck(
                check_name="Helm Chart Integrity",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                remediation=f"Error validating Helm chart: {e}",
                details={"error": str(e)},
            )

    def _check_gitops_config(self) -> DeploymentCheck:
        start = time.perf_counter()
        details: dict[str, Any] = {}

        values_path = os.path.join(self.project_root, "deployment", "helm", "values.yaml")
        if os.path.isfile(values_path):
            try:
                import yaml
                with open(values_path, "r", encoding="utf-8") as f:
                    values = yaml.safe_load(f)
                argocd = values.get("argocd", {})
                details["argocd_enabled"] = argocd.get("enabled", False)
                network_policy = values.get("networkPolicy", {})
                details["network_policy_enabled"] = network_policy.get("enabled", False)
                service_mesh = values.get("global", {}).get("serviceMesh", {})
                details["service_mesh_provider"] = service_mesh.get("provider", "none")
            except Exception as e:
                details["parse_error"] = str(e)

        if not details.get("argocd_enabled", False):
            return DeploymentCheck(
                check_name="GitOps Configuration",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                remediation="Enable ArgoCD in values.yaml for GitOps deployment",
                details=details,
            )

        return DeploymentCheck(
            check_name="GitOps Configuration",
            passed=True,
            duration_ms=(time.perf_counter() - start) * 1000,
            details=details,
        )

    def _check_network_policies(self) -> DeploymentCheck:
        start = time.perf_counter()

        values_path = os.path.join(self.project_root, "deployment", "helm", "values.yaml")
        if not os.path.isfile(values_path):
            return DeploymentCheck(
                check_name="Network Policies",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                remediation="Add Helm values.yaml with network policy configuration",
                details={},
            )

        try:
            import yaml
            with open(values_path, "r", encoding="utf-8") as f:
                values = yaml.safe_load(f)

            network_policy = values.get("networkPolicy", {})
            enabled = network_policy.get("enabled", False)
            default_deny = network_policy.get("defaultDeny", False)

            details = {
                "enabled": enabled,
                "default_deny": default_deny,
            }

            if not enabled:
                return DeploymentCheck(
                    check_name="Network Policies",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    remediation="Enable network policies in values.yaml (networkPolicy.enabled: true)",
                    details=details,
                )

            if not default_deny:
                return DeploymentCheck(
                    check_name="Network Policies",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    remediation="Set networkPolicy.defaultDeny to true for zero-trust networking",
                    details=details,
                )

            return DeploymentCheck(
                check_name="Network Policies",
                passed=True,
                duration_ms=(time.perf_counter() - start) * 1000,
                details=details,
            )
        except Exception as e:
            return DeploymentCheck(
                check_name="Network Policies",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                remediation=f"Error checking network policies: {e}",
                details={"error": str(e)},
            )

    def _check_resource_limits(self) -> DeploymentCheck:
        start = time.perf_counter()

        values_path = os.path.join(self.project_root, "deployment", "helm", "values.yaml")
        if not os.path.isfile(values_path):
            return DeploymentCheck(
                check_name="Resource Limits",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                remediation="Add resource limits configuration in values.yaml",
                details={},
            )

        try:
            import yaml
            with open(values_path, "r", encoding="utf-8") as f:
                values = yaml.safe_load(f)

            services_to_check = ["api", "ai", "risk", "execution", "portfolio", "strategy"]
            missing_limits: list[str] = []
            details: dict[str, Any] = {}

            for svc in services_to_check:
                svc_config = values.get(svc, {})
                resources = svc_config.get("resources", {})
                requests = resources.get("requests", {})
                limits = resources.get("limits", {})

                has_requests = "cpu" in requests and "memory" in requests
                has_limits = "cpu" in limits and "memory" in limits

                if not has_requests or not has_limits:
                    missing_limits.append(svc)

                details[svc] = {
                    "has_requests": has_requests,
                    "has_limits": has_limits,
                }

            if missing_limits:
                return DeploymentCheck(
                    check_name="Resource Limits",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    remediation=f"Add CPU/memory requests and limits for: {', '.join(missing_limits)}",
                    details=details,
                )

            return DeploymentCheck(
                check_name="Resource Limits",
                passed=True,
                duration_ms=(time.perf_counter() - start) * 1000,
                details=details,
            )
        except Exception as e:
            return DeploymentCheck(
                check_name="Resource Limits",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                remediation=f"Error checking resource limits: {e}",
                details={"error": str(e)},
            )

    def _check_health_probes(self) -> DeploymentCheck:
        start = time.perf_counter()

        values_path = os.path.join(self.project_root, "deployment", "helm", "values.yaml")
        if not os.path.isfile(values_path):
            return DeploymentCheck(
                check_name="Health Probes",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                remediation="Add health probe configuration in values.yaml",
                details={},
            )

        try:
            import yaml
            with open(values_path, "r", encoding="utf-8") as f:
                values = yaml.safe_load(f)

            services_to_check = ["api", "ai", "risk", "execution"]
            missing_probes: list[str] = []
            details: dict[str, Any] = {}

            for svc in services_to_check:
                svc_config = values.get(svc, {})
                has_liveness = "livenessProbe" in svc_config
                has_readiness = "readinessProbe" in svc_config

                if not has_liveness or not has_readiness:
                    missing_probes.append(svc)

                details[svc] = {
                    "has_liveness_probe": has_liveness,
                    "has_readiness_probe": has_readiness,
                }

            if missing_probes:
                return DeploymentCheck(
                    check_name="Health Probes",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    remediation=f"Add livenessProbe and readinessProbe for: {', '.join(missing_probes)}",
                    details=details,
                )

            return DeploymentCheck(
                check_name="Health Probes",
                passed=True,
                duration_ms=(time.perf_counter() - start) * 1000,
                details=details,
            )
        except Exception as e:
            return DeploymentCheck(
                check_name="Health Probes",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                remediation=f"Error checking health probes: {e}",
                details={"error": str(e)},
            )

    @staticmethod
    def _find_yaml_files(directory: str) -> list[str]:
        yaml_files: list[str] = []
        for root, dirs, files in os.walk(directory):
            for f in files:
                if f.endswith((".yaml", ".yml")):
                    yaml_files.append(os.path.join(root, f))
        return yaml_files