"""Marketplace validation.

Provides :class:`MarketplaceValidator` for validating marketplace
packages, manifests, structure, signatures, compatibility,
permissions, and dependencies.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REQUIRED_PACKAGE_FILES = ["manifest.json", "plugin.py"]


class MarketplaceValidator:
    """Validates marketplace packages and their components.

    Each ``validate_*`` method returns a list of error strings (empty
    when valid).  :meth:`validate_package` runs all checks and returns
    a structured result dictionary with a ``valid`` flag and per-section
    error lists.
    """

    def __init__(self) -> None:
        self._validation_count: int = 0
        self._error_count: int = 0
        self._last_errors: List[str] = []

    def validate_package(self, package_path: str) -> Dict[str, Any]:
        """Run all validations on a package.

        Args:
            package_path: Path to the package directory or archive.

        Returns:
            A dictionary with:

            - ``valid`` (bool): Overall pass/fail.
            - ``errors`` (list): Combined error messages.
            - ``structure_errors`` (list): Structure-specific errors.
            - ``manifest_errors`` (list): Manifest-specific errors.
            - ``signature_errors`` (list): Signature-specific errors.
            - ``compatibility_errors`` (list): Compatibility errors.
            - ``permission_errors`` (list): Permission errors.
            - ``dependency_errors`` (list): Dependency errors.
        """
        self._validation_count += 1

        structure_errors = self.validate_structure(package_path)

        manifest_path = os.path.join(package_path, "manifest.json")
        manifest_data: Dict[str, Any] = {}
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as fh:
                    manifest_data = json.load(fh)
            except (json.JSONDecodeError, IOError) as exc:
                manifest_data = {}
                structure_errors.append(
                    f"Failed to parse manifest.json: {exc}"
                )

        manifest_errors = self.validate_manifest(manifest_data)
        signature_errors = self.validate_signature(package_path)
        compatibility_errors = self.validate_compatibility(manifest_data)
        permission_errors = self.validate_permissions(manifest_data)
        dependency_errors = self.validate_dependencies(manifest_data)

        all_errors: List[str] = []
        all_errors.extend(structure_errors)
        all_errors.extend(manifest_errors)
        all_errors.extend(signature_errors)
        all_errors.extend(compatibility_errors)
        all_errors.extend(permission_errors)
        all_errors.extend(dependency_errors)

        valid = len(all_errors) == 0
        if not valid:
            self._error_count += 1

        self._last_errors = list(all_errors)

        return {
            "valid": valid,
            "errors": all_errors,
            "structure_errors": structure_errors,
            "manifest_errors": manifest_errors,
            "signature_errors": signature_errors,
            "compatibility_errors": compatibility_errors,
            "permission_errors": permission_errors,
            "dependency_errors": dependency_errors,
        }

    def validate_manifest(
        self, manifest_data: Dict[str, Any]
    ) -> List[str]:
        """Validate a package manifest dictionary.

        Args:
            manifest_data: The manifest data dictionary.

        Returns:
            List of error messages; empty when valid.
        """
        errors: List[str] = []
        if not manifest_data or not isinstance(manifest_data, dict):
            errors.append("Manifest data is empty or not a dictionary")
            return errors

        required_fields = ["id", "name", "version", "api"]
        for field in required_fields:
            if not manifest_data.get(field):
                errors.append(
                    f"Manifest field '{field}' is required"
                )

        manifest_id = manifest_data.get("id", "")
        if manifest_id and not self._is_valid_id(manifest_id):
            errors.append(
                f"Manifest 'id' contains invalid characters: "
                f"{manifest_id!r}"
            )

        version = manifest_data.get("version", "")
        if version and not self._is_valid_version(version):
            errors.append(
                f"Manifest 'version' is not a valid version: "
                f"{version!r}"
            )

        return errors

    def validate_structure(self, package_path: str) -> List[str]:
        """Check that a package has the required files and structure.

        Args:
            package_path: Path to the package directory.

        Returns:
            List of error messages; empty when valid.
        """
        errors: List[str] = []
        if not package_path:
            errors.append("Package path cannot be empty")
            return errors

        path = Path(package_path)
        if not path.exists():
            errors.append(
                f"Package path does not exist: {package_path}"
            )
            return errors

        if not path.is_dir():
            errors.append(
                f"Package path is not a directory: {package_path}"
            )
            return errors

        if not os.access(str(path), os.R_OK):
            errors.append(
                f"Package directory is not readable: {package_path}"
            )
            return errors

        for name in REQUIRED_PACKAGE_FILES:
            if not (path / name).is_file():
                errors.append(
                    f"Required file '{name}' missing in package"
                )

        return errors

    def validate_signature(self, package_path: str) -> List[str]:
        """Validate that a package has a valid signature file.

        Args:
            package_path: Path to the package directory.

        Returns:
            List of error messages; empty when valid.
        """
        errors: List[str] = []
        signature_path = os.path.join(package_path, "signature.sig")
        manifest_path = os.path.join(package_path, "manifest.json")

        if not os.path.exists(manifest_path):
            return errors

        if not os.path.exists(signature_path):
            errors.append(
                "Package is missing signature.sig file"
            )
            return errors

        try:
            with open(signature_path, "r", encoding="utf-8") as fh:
                sig_content = fh.read().strip()
            if not sig_content:
                errors.append("Signature file is empty")
        except (IOError, OSError) as exc:
            errors.append(
                f"Failed to read signature file: {exc}"
            )

        return errors

    def validate_compatibility(
        self, manifest_data: Dict[str, Any]
    ) -> List[str]:
        """Validate API and dependency compatibility.

        Args:
            manifest_data: The manifest data dictionary.

        Returns:
            List of error messages; empty when compatible.
        """
        errors: List[str] = []
        if not manifest_data:
            return errors

        api_version = manifest_data.get("api", "")
        if api_version:
            supported = ["v1", "v2"]
            if api_version not in supported:
                errors.append(
                    f"Unsupported API version: {api_version!r}. "
                    f"Supported: {supported}"
                )

        min_qt_version = manifest_data.get("min_icyquant_version", "")
        if min_qt_version:
            logger.debug(
                "Package requires ICYQuant >= %s", min_qt_version
            )

        return errors

    def validate_permissions(
        self, manifest_data: Dict[str, Any]
    ) -> List[str]:
        """Validate permission declarations in a manifest.

        Args:
            manifest_data: The manifest data dictionary.

        Returns:
            List of error messages; empty when permissions are
            well-formed.
        """
        errors: List[str] = []
        if not manifest_data:
            return errors

        permissions = manifest_data.get("permissions", [])
        if permissions is None:
            return errors

        if not isinstance(permissions, list):
            errors.append("Permissions must be a list")
            return errors

        known_permissions = {
            "filesystem.read",
            "filesystem.write",
            "network",
            "process",
            "registry.read",
            "registry.write",
            "ui.access",
            "data.access",
        }

        for perm in permissions:
            if not isinstance(perm, str) or not perm:
                errors.append(
                    f"Invalid permission value: {perm!r}"
                )
            elif perm not in known_permissions:
                logger.debug(
                    "Unknown permission '%s' found in manifest",
                    perm,
                )

        return errors

    def validate_dependencies(
        self,
        manifest_data: Dict[str, Any],
        available: Optional[List[str]] = None,
    ) -> List[str]:
        """Validate dependency declarations against available plugins.

        Optional dependencies are prefixed with ``?`` and are not
        required to be present.

        Args:
            manifest_data: The manifest data dictionary.
            available: List of available plugin ids. When ``None``,
                only structural validation is performed.

        Returns:
            List of error messages; empty when all dependencies
            are satisfied.
        """
        errors: List[str] = []
        if not manifest_data:
            return errors

        deps = manifest_data.get("dependencies", [])
        if deps is None:
            return errors

        if not isinstance(deps, list):
            errors.append("Dependencies must be a list")
            return errors

        available_set = set(available) if available else set()
        seen: set = set()

        for dep in deps:
            if not isinstance(dep, str) or not dep:
                errors.append(f"Invalid dependency entry: {dep!r}")
                continue

            dep_name = dep.strip()
            optional = dep_name.startswith("?")
            if optional:
                dep_name = dep_name[1:]

            if not dep_name:
                errors.append(f"Invalid dependency entry: {dep!r}")
                continue

            if dep_name in seen:
                errors.append(f"Duplicate dependency: {dep_name!r}")
                continue
            seen.add(dep_name)

            if optional:
                if available and dep_name not in available_set:
                    logger.debug(
                        "Optional dependency '%s' not found "
                        "(non-fatal).",
                        dep_name,
                    )
                continue

            if available is not None and dep_name not in available_set:
                errors.append(
                    f"Required dependency '{dep_name}' is not available"
                )

        return errors

    def get_stats(self) -> Dict[str, Any]:
        """Return validator statistics.

        Returns:
            A dictionary with validation counts and error rate.
        """
        return {
            "total_validations": self._validation_count,
            "total_errors": self._error_count,
            "error_rate": (
                self._error_count / self._validation_count
                if self._validation_count > 0
                else 0.0
            ),
            "last_errors": list(self._last_errors),
        }

    @staticmethod
    def _is_valid_id(plugin_id: str) -> bool:
        """Check whether a string is a valid plugin identifier."""
        if not plugin_id:
            return False
        for part in plugin_id.split("."):
            if not part:
                return False
            cleaned = part.replace("_", "").replace("-", "")
            if not cleaned.isalnum():
                return False
        return True

    @staticmethod
    def _is_valid_version(version: str) -> bool:
        """Check whether a string is a valid version (e.g. 1.0.0)."""
        if not version:
            return False
        parts = version.split(".")
        if len(parts) < 1 or len(parts) > 4:
            return False
        for part in parts:
            if not part.isdigit():
                return False
        return True