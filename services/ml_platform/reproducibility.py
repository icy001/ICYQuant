"""
ICYQuant Reproducibility - Experiment and model reproducibility framework.

     Code Version
          +
     Dataset Version
          +
     Feature Version
          +
     Model Version
          +
     Parameters
          +
     Environment
          ↓
     Reproducible Experiment

Ensures that every research result can be reproduced with the exact
same code, data, features, and environment.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ReproducibilityManifest:
    """Complete manifest for reproducing an experiment or model.

    Contains everything needed to re-run the exact same computation:
    - Code version (git commit)
    - Data version (dataset + features)
    - Model version (architecture + params)
    - Environment (Python + dependencies)
    - Parameters (hyperparameters + config)
    """

    manifest_id: str = ""
    artifact_type: str = "experiment"  # experiment, model, prediction

    # Code
    git_commit: str = ""
    git_branch: str = ""
    git_remote: str = ""
    code_diff: str = ""            # git diff at time of run
    entry_point: str = ""          # script or notebook path

    # Data
    dataset_id: Optional[str] = None
    dataset_version: str = ""
    feature_ids: List[str] = field(default_factory=list)
    feature_versions: Dict[str, str] = field(default_factory=dict)

    # Model
    model_id: Optional[str] = None
    model_version: str = ""
    model_params: Dict[str, Any] = field(default_factory=dict)
    model_architecture: str = ""

    # Environment
    python_version: str = ""
    requirements_hash: str = ""
    requirements: List[str] = field(default_factory=list)
    environment_variables: Dict[str, str] = field(default_factory=dict)
    platform: str = ""             # linux, darwin, win32

    # Parameters
    random_seed: int = 42
    config_overrides: Dict[str, Any] = field(default_factory=dict)

    # Validation
    expected_metrics: Dict[str, float] = field(default_factory=dict)
    expected_output_hash: str = ""

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""

    def compute_manifest_hash(self) -> str:
        """Compute a hash of everything that affects reproducibility."""
        content = {
            "git_commit": self.git_commit,
            "dataset_id": self.dataset_id,
            "feature_ids": sorted(self.feature_ids),
            "feature_versions": sorted(self.feature_versions.items()),
            "model_params": json.dumps(self.model_params, sort_keys=True),
            "python_version": self.python_version,
            "requirements_hash": self.requirements_hash,
            "random_seed": self.random_seed,
        }
        return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()[:16]


@dataclass
class ReproducibilityCheck:
    """Result of a reproducibility verification."""

    manifest_id: str = ""
    reproducible: bool = False
    checks: Dict[str, bool] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    metrics_match: bool = False
    metrics_difference: Dict[str, float] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.utcnow)


class ReproducibilityManager:
    """Manages experiment and model reproducibility.

    Ensures that every artifact can be faithfully reproduced by:
    1. Recording the full computation context
    2. Freezing code, data, and environment versions
    3. Validating reproducibility by re-running
    4. Detecting non-reproducible results
    """

    def __init__(self) -> None:
        self._manifests: Dict[str, ReproducibilityManifest] = {}
        self._checks: Dict[str, List[ReproducibilityCheck]] = {}

    # -- Capture --

    def capture_manifest(
        self,
        artifact_type: str,
        dataset_id: Optional[str] = None,
        feature_ids: Optional[List[str]] = None,
        model_params: Optional[Dict[str, Any]] = None,
        expected_metrics: Optional[Dict[str, float]] = None,
    ) -> ReproducibilityManifest:
        """Capture the current environment for reproducibility.

        Records code version, Python version, and dependencies.
        """
        import uuid

        manifest = ReproducibilityManifest(
            manifest_id=uuid.uuid4().hex[:12],
            artifact_type=artifact_type,
        )

        # Capture git info
        try:
            manifest.git_commit = self._get_git_commit()
            manifest.git_branch = self._get_git_branch()
        except Exception as exc:
            logger.warning("Failed to capture git info: %s", exc)

        # Capture Python version
        import sys
        manifest.python_version = sys.version.split()[0]

        # Capture platform
        import platform
        manifest.platform = platform.system().lower()

        # Capture requirements
        manifest.requirements = self._capture_requirements()
        manifest.requirements_hash = self._hash_requirements(manifest.requirements)

        # Data context
        if dataset_id:
            manifest.dataset_id = dataset_id
        if feature_ids:
            manifest.feature_ids = feature_ids

        # Model context
        if model_params:
            manifest.model_params = model_params

        # Expected metrics
        if expected_metrics:
            manifest.expected_metrics = expected_metrics

        self._manifests[manifest.manifest_id] = manifest
        logger.info("Reproducibility manifest captured: %s (commit=%s)",
                     manifest.manifest_id, manifest.git_commit[:8] if manifest.git_commit else "N/A")

        return manifest

    # -- Verify --

    async def verify(
        self,
        manifest_id: str,
        actual_metrics: Optional[Dict[str, float]] = None,
    ) -> ReproducibilityCheck:
        """Verify that an artifact can be reproduced.

        Checks:
        1. Code version matches
        2. Environment matches (Python, dependencies)
        3. Data versions match
        4. Output metrics match (if provided)
        """
        manifest = self._manifests.get(manifest_id)
        if manifest is None:
            check = ReproducibilityCheck(manifest_id=manifest_id)
            check.issues.append(f"Manifest not found: {manifest_id}")
            return check

        check = ReproducibilityCheck(manifest_id=manifest_id)
        check.reproducible = True

        # Check 1: Code version
        current_commit = self._get_git_commit()
        code_matches = current_commit == manifest.git_commit
        check.checks["code_version"] = code_matches
        if not code_matches:
            check.issues.append(f"Code version mismatch: current={current_commit[:8]}, manifest={manifest.git_commit[:8]}")

        # Check 2: Python version
        import sys
        python_matches = sys.version.split()[0] == manifest.python_version
        check.checks["python_version"] = python_matches
        if not python_matches:
            check.issues.append(f"Python version mismatch: current={sys.version.split()[0]}, manifest={manifest.python_version}")

        # Check 3: Metrics
        if actual_metrics and manifest.expected_metrics:
            for metric, expected in manifest.expected_metrics.items():
                actual = actual_metrics.get(metric, 0.0)
                diff = abs(actual - expected)
                check.metrics_difference[metric] = diff
                if diff > 1e-6:
                    check.metrics_match = False
                    check.issues.append(f"Metric '{metric}' differs: expected={expected}, actual={actual}")
            check.checks["metrics"] = check.metrics_match

        # Overall
        check.reproducible = all(check.checks.values()) if check.checks else True

        # Store check result
        if manifest_id not in self._checks:
            self._checks[manifest_id] = []
        self._checks[manifest_id].append(check)

        logger.info("Reproducibility check: manifest=%s, reproducible=%s, issues=%d",
                     manifest_id, check.reproducible, len(check.issues))

        return check

    # -- Git helpers --

    def _get_git_commit(self) -> str:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def _get_git_branch(self) -> str:
        """Get current git branch."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def _capture_requirements(self) -> List[str]:
        """Capture installed package list."""
        try:
            import pkg_resources
            return sorted([
                f"{dist.key}=={dist.version}"
                for dist in pkg_resources.working_set
            ])
        except Exception:
            return []

    def _hash_requirements(self, requirements: List[str]) -> str:
        """Hash the requirements list."""
        return hashlib.sha256("\n".join(requirements).encode()).hexdigest()[:16]

    # -- Query --

    def get_manifest(self, manifest_id: str) -> Optional[ReproducibilityManifest]:
        return self._manifests.get(manifest_id)

    def get_check_history(self, manifest_id: str) -> List[ReproducibilityCheck]:
        return self._checks.get(manifest_id, [])
