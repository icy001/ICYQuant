"""
Environment detector.

Auto-detects the current runtime environment
by checking multiple sources in priority order:

    CLI Arguments
        ↓
    Environment Variables
        ↓
    Docker Container
        ↓
    Kubernetes
        ↓
    Default (development)
"""

from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional

from ..discovery import EnvironmentDiscovery


class EnvironmentDetector:
    """
    Detects the current environment.

    Checks multiple sources in priority order
    to determine which environment profile to use.

    Detection Priority:
    1. CLI arguments (--env=production)
    2. ICYQUANT_ENV environment variable
    3. Docker (icyquant.env label)
    4. Kubernetes (icyquant.env annotation)
    5. Default (development)

    Usage:
        detector = EnvironmentDetector()
        env_name = detector.detect()
    """

    # Valid environment names
    VALID_ENVIRONMENTS = [
        "development",
        "testing",
        "staging",
        "production",
    ]

    # Environment variable names to check
    ENV_VAR_NAMES = [
        "ICYQUANT_ENV",
        "ICYQUANT_ENVIRONMENT",
        "APP_ENV",
        "ENVIRONMENT",
        "NODE_ENV",
    ]

    def __init__(
        self,
        args: Optional[List[str]] = None,
        discovery: Optional[EnvironmentDiscovery] = None,
    ) -> None:
        """
        Initialize detector.

        Args:
            args: Command-line arguments.
            discovery: EnvironmentDiscovery instance.
        """
        self._args = args or sys.argv[1:]
        self._discovery = discovery or EnvironmentDiscovery()
        self._detection_log: List[Dict[str, str]] = []

    def detect(
        self,
    ) -> str:
        """
        Detect the current environment.

        Returns:
            Environment name (e.g., "development").
        """
        self._detection_log = []

        # 1. Check CLI arguments
        cli_env = self._detect_from_cli()
        if cli_env:
            self._log("cli", cli_env)
            return cli_env

        # 2. Check environment variables
        env_env = self._detect_from_env()
        if env_env:
            self._log("env", env_env)
            return env_env

        # 3. Check Docker
        docker_env = self._detect_from_docker()
        if docker_env:
            self._log("docker", docker_env)
            return docker_env

        # 4. Check Kubernetes
        k8s_env = self._detect_from_kubernetes()
        if k8s_env:
            self._log("kubernetes", k8s_env)
            return k8s_env

        # 5. Default
        self._log("default", "development")
        return "development"

    def _detect_from_cli(
        self,
    ) -> Optional[str]:
        """Detect environment from CLI arguments."""
        for arg in self._args:
            if arg.startswith("--env="):
                value = arg.split("=", 1)[1]
                if self._is_valid(value):
                    return value
            elif arg.startswith("--environment="):
                value = arg.split("=", 1)[1]
                if self._is_valid(value):
                    return value

        # Check -e <value> format
        i = 0
        while i < len(self._args):
            if self._args[i] in ("--env", "--environment", "-e"):
                if i + 1 < len(self._args):
                    value = self._args[i + 1]
                    if self._is_valid(value):
                        return value
            i += 1

        return None

    def _detect_from_env(
        self,
    ) -> Optional[str]:
        """Detect environment from environment variables."""
        for var_name in self.ENV_VAR_NAMES:
            value = os.environ.get(var_name)
            if value and self._is_valid(value):
                return value
        return None

    def _detect_from_docker(
        self,
    ) -> Optional[str]:
        """Detect environment from Docker labels."""
        return self._discovery.detect_docker_env()

    def _detect_from_kubernetes(
        self,
    ) -> Optional[str]:
        """Detect environment from Kubernetes annotations."""
        return self._discovery.detect_kubernetes_env()

    def _is_valid(
        self,
        env_name: str,
    ) -> bool:
        """Check if environment name is valid."""
        return env_name.lower() in self.VALID_ENVIRONMENTS

    def _log(
        self,
        source: str,
        value: str,
    ) -> None:
        """Log a detection result."""
        self._detection_log.append({
            "source": source,
            "value": value,
        })

    def get_detection_log(
        self,
    ) -> List[Dict[str, str]]:
        """Get detection log."""
        return list(self._detection_log)
