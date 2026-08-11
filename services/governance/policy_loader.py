"""
Policy Loader — loads policy versions from various sources into the repository.

Supports multiple input formats:
  - Python dicts (programmatic definition)
  - JSON files
  - YAML files
  - Remote HTTP/API endpoints (future)
  - Database (future)

The loader validates loaded policies before inserting them into the
repository, ensuring only well-formed policy versions enter the system.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .policy_version import PolicyVersion
from .policy_repository import PolicyRepository
from .policy_status import PolicyLifecycleStatus
from .policy_exception import PolicyLoadException


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

@dataclass
class PolicyLoader:
    """
    Loads policy versions from structured data into a repository.

    Supports:
      - Dict-based loading (programmatic)
      - JSON file loading
      - YAML file loading (if PyYAML is available)
      - Validation of loaded policies
      - Batch loading with partial failure tolerance
    """

    repository: Optional[PolicyRepository] = None

    # Load statistics
    load_count: int = 0
    error_count: int = 0
    last_error: str = ""
    last_load_at: Optional[float] = None

    # ------------------------------------------------------------------
    # Dict loading
    # ------------------------------------------------------------------

    def load_dict(
        self, data: Dict[str, Any], actor: str = "SYSTEM"
    ) -> PolicyVersion:
        """
        Load a policy version from a dict.

        Validates the version before storing it.
        """
        try:
            version = PolicyVersion.from_dict(data)
            self._validate_version(version)

            if self.repository:
                self.repository.save(version, actor)

            self.load_count += 1
            self.last_load_at = time.time()
            return version

        except Exception as e:
            self.error_count += 1
            self.last_error = str(e)
            raise PolicyLoadException(
                policy_id=data.get("policy_id", ""),
                version_id=data.get("version_id", ""),
                storage_error=str(e),
            ) from e

    def load_dicts(
        self,
        data_list: List[Dict[str, Any]],
        actor: str = "SYSTEM",
        stop_on_error: bool = False,
    ) -> List[PolicyVersion]:
        """
        Load multiple policy versions from dicts.

        Args:
            data_list: List of policy version dicts.
            actor: Actor performing the load.
            stop_on_error: If True, stops on first error.
                            If False, continues loading remaining items.

        Returns:
            List of successfully loaded PolicyVersion objects.
        """
        results: List[PolicyVersion] = []
        for data in data_list:
            try:
                version = self.load_dict(data, actor)
                results.append(version)
            except PolicyLoadException:
                if stop_on_error:
                    raise
                # Continue with next item
        return results

    # ------------------------------------------------------------------
    # JSON loading
    # ------------------------------------------------------------------

    def load_json_file(
        self, filepath: str, actor: str = "SYSTEM"
    ) -> List[PolicyVersion]:
        """
        Load policies from a JSON file.

        The JSON file should contain either:
          - A single policy object: { "policy_id": "...", ... }
          - An array of policy objects: [ { ... }, { ... } ]
          - A structured document: { "policies": [ ... ], "metadata": { ... } }
        """
        if not os.path.exists(filepath):
            raise PolicyLoadException(
                policy_id="",
                storage_error=f"File not found: {filepath}",
            )

        with open(filepath, "r", encoding="utf-8") as f:
            content = json.load(f)

        # Determine structure
        if isinstance(content, list):
            items = content
        elif isinstance(content, dict) and "policies" in content:
            items = content["policies"]
        else:
            items = [content]

        return self.load_dicts(items, actor)

    def load_json_string(
        self, json_str: str, actor: str = "SYSTEM"
    ) -> List[PolicyVersion]:
        """Load policies from a JSON string."""
        content = json.loads(json_str)

        if isinstance(content, list):
            items = content
        elif isinstance(content, dict) and "policies" in content:
            items = content["policies"]
        else:
            items = [content]

        return self.load_dicts(items, actor)

    # ------------------------------------------------------------------
    # YAML loading (optional)
    # ------------------------------------------------------------------

    def load_yaml_file(
        self, filepath: str, actor: str = "SYSTEM"
    ) -> List[PolicyVersion]:
        """
        Load policies from a YAML file.

        Requires PyYAML to be installed.
        """
        try:
            import yaml
        except ImportError:
            raise PolicyLoadException(
                policy_id="",
                storage_error="PyYAML is required for YAML loading. Install with: pip install pyyaml",
            )

        if not os.path.exists(filepath):
            raise PolicyLoadException(
                policy_id="",
                storage_error=f"File not found: {filepath}",
            )

        with open(filepath, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)

        if isinstance(content, list):
            items = content
        elif isinstance(content, dict) and "policies" in content:
            items = content["policies"]
        else:
            items = [content]

        return self.load_dicts(items, actor)

    # ------------------------------------------------------------------
    # Bulk loading from directory
    # ------------------------------------------------------------------

    def load_directory(
        self,
        directory: str,
        pattern: str = "*.json",
        actor: str = "SYSTEM",
    ) -> Dict[str, List[PolicyVersion]]:
        """
        Load all policy files from a directory.

        Returns a dict mapping filename → loaded versions.
        """
        import glob

        results: Dict[str, List[PolicyVersion]] = {}

        search_path = os.path.join(directory, pattern)
        for filepath in sorted(glob.glob(search_path)):
            try:
                if filepath.endswith(".json"):
                    versions = self.load_json_file(filepath, actor)
                elif filepath.endswith(".yaml") or filepath.endswith(".yml"):
                    versions = self.load_yaml_file(filepath, actor)
                else:
                    continue
                results[os.path.basename(filepath)] = versions
            except PolicyLoadException:
                # Record and continue
                results[os.path.basename(filepath)] = []

        return results

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_version(version: PolicyVersion) -> None:
        """
        Validate a policy version before storing.

        Checks:
          - Must have a policy_id
          - Must have a non-empty name
          - Must have at least one rule
          - Status must be a valid lifecycle status
        """
        if not version.policy_id:
            raise ValueError("Policy version must have a policy_id")

        if not version.name:
            raise ValueError("Policy version must have a name")

        if not version.rules:
            raise ValueError(f"Policy '{version.name}' must have at least one rule")

        # Status must be valid
        if not isinstance(version.status, PolicyLifecycleStatus):
            raise ValueError(
                f"Invalid status for policy '{version.name}': {version.status}"
            )

    # ------------------------------------------------------------------
    # Builder pattern
    # ------------------------------------------------------------------

    @staticmethod
    def build_version(
        policy_id: str,
        name: str,
        description: str = "",
        scope: str = "GLOBAL",
        version: str = "1.0.0",
        **kwargs,
    ) -> PolicyVersion:
        """Build a policy version programmatically with validation."""
        pv = PolicyVersion(
            policy_id=policy_id,
            name=name,
            description=description,
            scope=scope,
            version=version,
            **kwargs,
        )
        PolicyLoader._validate_version(pv)
        return pv

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def load_summary(self) -> Dict[str, Any]:
        return {
            "load_count": self.load_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "last_load_at": self.last_load_at,
        }
