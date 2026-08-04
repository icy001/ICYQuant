"""
Environment discovery.

Auto-detects the current runtime environment
by checking for Docker, Kubernetes, CI/CD
environment variables, and local machine
indicators.
"""

from __future__ import annotations

import os
import socket
from typing import Any, Dict, List, Optional


class EnvironmentDiscovery:
    """
    Discovers the current runtime environment.

    Checks for:
    - Docker (via .dockerenv or cgroup)
    - Kubernetes (via service account)
    - GitHub Actions (via GITHUB_ACTIONS env var)
    - GitLab CI (via GITLAB_CI env var)
    - Local machine

    Usage:
        discovery = EnvironmentDiscovery()
        info = discovery.detect_all()
    """

    # Environment variable patterns for CI/CD
    CI_PATTERNS = {
        "github_actions": ["GITHUB_ACTIONS", "GITHUB_WORKFLOW"],
        "gitlab_ci": ["GITLAB_CI", "CI_PROJECT_ID"],
        "jenkins": ["JENKINS_HOME", "JOB_NAME"],
        "circleci": ["CIRCLECI"],
        "travis": ["TRAVIS"],
    }

    def __init__(
        self,
    ) -> None:
        self._docker_cached: Optional[bool] = None
        self._kubernetes_cached: Optional[bool] = None

    def detect_all(
        self,
    ) -> Dict[str, Any]:
        """
        Perform full environment discovery.

        Returns:
            Dictionary with all discovery results.
        """
        return {
            "is_docker": self.is_docker(),
            "is_kubernetes": self.is_kubernetes(),
            "ci_provider": self.detect_ci_provider(),
            "hostname": socket.gethostname(),
            "platform": os.name,
            "container_id": self.get_container_id(),
        }

    def is_docker(
        self,
    ) -> bool:
        """
        Check if running inside Docker.

        Detection methods:
        1. Check for .dockerenv file
        2. Check cgroup for docker/containerd
        3. Check for common Docker env vars
        """
        if self._docker_cached is not None:
            return self._docker_cached

        # Method 1: Check .dockerenv
        if os.path.exists("/.dockerenv"):
            self._docker_cached = True
            return True

        # Method 2: Check cgroup
        try:
            with open("/proc/1/cgroup", "r") as f:
                content = f.read()
                if "docker" in content or "container" in content:
                    self._docker_cached = True
                    return True
        except (FileNotFoundError, PermissionError):
            pass

        # Method 3: Check environment variables
        docker_vars = [
            "DOCKER_CONTAINER",
            "CONTAINER_ID",
        ]
        for var in docker_vars:
            if os.environ.get(var):
                self._docker_cached = True
                return True

        self._docker_cached = False
        return False

    def is_kubernetes(
        self,
    ) -> bool:
        """
        Check if running in Kubernetes.

        Detection methods:
        1. Check for service account token
        2. Check for KUBERNETES_SERVICE_HOST
        3. Check for mounted service account
        """
        if self._kubernetes_cached is not None:
            return self._kubernetes_cached

        # Method 1: Check environment variable
        if os.environ.get("KUBERNETES_SERVICE_HOST"):
            self._kubernetes_cached = True
            return True

        # Method 2: Check for service account
        sa_token_path = (
            "/var/run/secrets/kubernetes.io/serviceaccount/token"
        )
        if os.path.exists(sa_token_path):
            self._kubernetes_cached = True
            return True

        # Method 3: Check for kube config
        if os.environ.get("KUBECONFIG"):
            self._kubernetes_cached = True
            return True

        self._kubernetes_cached = False
        return False

    def detect_ci_provider(
        self,
    ) -> Optional[str]:
        """
        Detect CI/CD provider.

        Returns:
            CI provider name or None.
        """
        for provider, env_vars in self.CI_PATTERNS.items():
            for var in env_vars:
                if os.environ.get(var):
                    return provider
        return None

    def get_container_id(
        self,
    ) -> Optional[str]:
        """
        Get container ID if running in a container.

        Returns:
            Container ID or None.
        """
        # Try Docker env var
        container_id = os.environ.get("CONTAINER_ID")
        if container_id:
            return container_id

        # Try to read from cgroup
        try:
            with open("/proc/1/cgroup", "r") as f:
                for line in f:
                    parts = line.strip().split("/")
                    for part in parts:
                        # Container IDs are typically 64-char hex
                        if len(part) == 64 and all(
                            c in "0123456789abcdef" for c in part
                        ):
                            return part
        except (FileNotFoundError, PermissionError):
            pass

        return None

    def detect_docker_env(
        self,
    ) -> Optional[str]:
        """
        Detect environment from Docker labels.

        Returns:
            Detected environment or None.
        """
        if not self.is_docker():
            return None

        # Check common Docker env vars
        env_vars = [
            "ICYQUANT_ENV",
            "APP_ENV",
            "ENVIRONMENT",
        ]
        for var in env_vars:
            value = os.environ.get(var)
            if value:
                return value

        return None

    def detect_kubernetes_env(
        self,
    ) -> Optional[str]:
        """
        Detect environment from Kubernetes annotations.

        Returns:
            Detected environment or None.
        """
        if not self.is_kubernetes():
            return None

        # Check environment variables injected by K8s
        env_vars = [
            "ICYQUANT_ENV",
            "APP_ENV",
            "ENVIRONMENT",
        ]
        for var in env_vars:
            value = os.environ.get(var)
            if value:
                return value

        return None

    def get_hostname(
        self,
    ) -> str:
        """Get the current hostname."""
        return socket.gethostname()
