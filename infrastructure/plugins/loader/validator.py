"""Loader validator for the plugin loader subsystem.

Provides validation of plugin manifests, entrypoints, dependencies,
and plugin directories. Returns lists of error strings; an empty
list indicates a valid object.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from ..manifest import PluginManifest

logger = logging.getLogger(__name__)


class LoaderValidator:
    """Validates manifests, entrypoints, dependencies, and directories.

    Each ``validate_*`` method returns a list of error strings (empty
    when valid). :meth:`validate_plugin` runs all checks and returns a
    structured result dictionary with a ``valid`` flag and per-section
    error lists.
    """

    def __init__(self) -> None:
        self._validation_count: int = 0
        self._error_count: int = 0
        self._last_errors: List[str] = []

    def validate_manifest(self, manifest: PluginManifest) -> List[str]:
        """Validate a plugin manifest.

        Args:
            manifest: The manifest to validate.

        Returns:
            List of error messages; empty when valid.
        """
        errors: List[str] = []
        if manifest is None:
            errors.append("Manifest is None")
            return errors

        if hasattr(manifest, "validate") and callable(manifest.validate):
            try:
                errors.extend(manifest.validate())
            except Exception as exc:
                errors.append(f"Manifest validation raised: {exc}")
            return errors

        if not getattr(manifest, "id", ""):
            errors.append("Manifest field 'id' is required")
        if not getattr(manifest, "name", ""):
            errors.append("Manifest field 'name' is required")
        if not getattr(manifest, "version", ""):
            errors.append("Manifest field 'version' is required")
        if not getattr(manifest, "api", ""):
            errors.append("Manifest field 'api' is required")
        return errors

    def validate_entrypoint(self, entrypoint: str) -> List[str]:
        """Validate an entrypoint string.

        Accepts either a dotted module path (``"foo.bar"``) or a
        ``"module:Class"`` reference. Returns a list of error
        messages; empty when valid.

        Args:
            entrypoint: The entrypoint string to validate.

        Returns:
            List of error messages; empty when valid.
        """
        errors: List[str] = []
        if not entrypoint or not isinstance(entrypoint, str):
            errors.append("Entrypoint must be a non-empty string")
            return errors

        if ":" in entrypoint:
            parts = entrypoint.split(":")
            if len(parts) != 2:
                errors.append(
                    f"Entrypoint format should be 'module:class', "
                    f"got: {entrypoint!r}"
                )
                return errors
            module_path, class_name = parts
            if not module_path:
                errors.append("Entrypoint module path cannot be empty")
            elif not self._is_valid_module_path(module_path):
                errors.append(
                    f"Entrypoint module path '{module_path}' "
                    f"contains invalid characters"
                )
            if not class_name:
                errors.append("Entrypoint class name cannot be empty")
            elif not class_name.isidentifier():
                errors.append(
                    f"Entrypoint class name '{class_name}' is not "
                    f"a valid identifier"
                )
        else:
            if not self._is_valid_module_path(entrypoint):
                errors.append(
                    f"Entrypoint '{entrypoint}' contains invalid "
                    f"characters"
                )
        return errors

    def validate_dependencies(
        self, deps: List[str], available: List[str]
    ) -> List[str]:
        """Validate dependency declarations against available plugins.

        Optional dependencies are prefixed with ``?`` and are not
        required to be present.

        Args:
            deps: List of dependency declarations.
            available: List of available plugin ids.

        Returns:
            List of error messages; empty when all dependencies
            are satisfied.
        """
        errors: List[str] = []
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
                if dep_name not in available_set:
                    logger.debug(
                        "Optional dependency '%s' not found "
                        "(non-fatal).",
                        dep_name,
                    )
                continue

            if dep_name not in available_set:
                errors.append(
                    f"Required dependency '{dep_name}' is not "
                    f"available"
                )

        return errors

    def validate_plugin(
        self,
        manifest: PluginManifest,
        deps: List[str],
        perms: List[str],
        caps: List[str],
    ) -> Dict[str, Any]:
        """Run all validations and return a structured result.

        Args:
            manifest: The plugin manifest to validate.
            deps: Dependency declarations.
            perms: Permission declarations.
            caps: Capability declarations.

        Returns:
            A dictionary with:

            - ``valid`` (bool): Overall pass/fail.
            - ``errors`` (list): Combined error messages.
            - ``manifest_errors`` (list): Manifest-specific errors.
            - ``entrypoint_errors`` (list): Entrypoint-specific errors.
            - ``dependency_errors`` (list): Dependency-specific errors.
            - ``permission_errors`` (list): Permission-specific errors.
            - ``capability_errors`` (list): Capability-specific errors.
        """
        self._validation_count += 1

        manifest_errors = self.validate_manifest(manifest)

        entrypoint = ""
        if manifest is not None:
            entrypoint = getattr(manifest, "entrypoint", "") or ""
        entrypoint_errors = self.validate_entrypoint(entrypoint)

        dependency_errors = self.validate_dependencies(
            deps, list(deps)
        )

        permission_errors = self._validate_permissions(perms)

        capability_errors = self._validate_capabilities(caps)

        all_errors = (
            manifest_errors
            + entrypoint_errors
            + dependency_errors
            + permission_errors
            + capability_errors
        )

        valid = len(all_errors) == 0
        if not valid:
            self._error_count += 1

        self._last_errors = list(all_errors)

        return {
            "valid": valid,
            "errors": all_errors,
            "manifest_errors": manifest_errors,
            "entrypoint_errors": entrypoint_errors,
            "dependency_errors": dependency_errors,
            "permission_errors": permission_errors,
            "capability_errors": capability_errors,
        }

    def validate_plugin_directory(self, plugin_dir: str) -> List[str]:
        """Validate a plugin directory structure.

        Checks that the directory exists, is accessible, and contains
        a recognisable manifest file.

        Args:
            plugin_dir: Path to the plugin directory.

        Returns:
            List of error messages; empty when valid.
        """
        errors: List[str] = []

        if not plugin_dir:
            errors.append("Plugin directory path cannot be empty")
            return errors

        path = Path(plugin_dir)
        if not path.exists():
            errors.append(f"Plugin directory does not exist: {plugin_dir}")
            return errors

        if not path.is_dir():
            errors.append(
                f"Plugin path is not a directory: {plugin_dir}"
            )
            return errors

        if not os.access(str(path), os.R_OK):
            errors.append(
                f"Plugin directory is not readable: {plugin_dir}"
            )
            return errors

        manifest_found = False
        for name in ("manifest.yaml", "manifest.yml"):
            if (path / name).is_file():
                manifest_found = True
                break

        if not manifest_found:
            errors.append(
                f"No manifest file found in plugin directory: "
                f"{plugin_dir}"
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

    def _validate_permissions(self, perms: List[str]) -> List[str]:
        """Validate permission declarations (internal)."""
        errors: List[str] = []
        if perms is None:
            return errors
        if not isinstance(perms, list):
            errors.append("Permissions must be a list")
            return errors
        for perm in perms:
            if not isinstance(perm, str) or not perm:
                errors.append(f"Invalid permission value: {perm!r}")
        return errors

    def _validate_capabilities(self, caps: List[str]) -> List[str]:
        """Validate capability declarations (internal)."""
        errors: List[str] = []
        if caps is None:
            return errors
        if not isinstance(caps, list):
            errors.append("Capabilities must be a list")
            return errors
        seen: set = set()
        for cap in caps:
            if not isinstance(cap, str) or not cap:
                errors.append(f"Invalid capability value: {cap!r}")
                continue
            if cap in seen:
                errors.append(f"Duplicate capability: {cap!r}")
                continue
            seen.add(cap)
        return errors

    @staticmethod
    def _is_valid_module_path(path: str) -> bool:
        """Check whether a string is a valid dotted module path."""
        if not path:
            return False
        for part in path.split("."):
            if not part:
                return False
            cleaned = part.replace("_", "").replace("-", "")
            if not cleaned.isalnum():
                return False
        return True