"""Plugin verifier for the loader subsystem.

Performs comprehensive verification of a plugin before it is loaded,
combining manifest validity, entrypoint format, API compatibility,
dependency availability, permission declarations, and signature
checks into a single result dictionary.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Set

from ..manifest import PluginManifest
from .validator import LoaderValidator

logger = logging.getLogger(__name__)


class PluginVerifier:
    """Verifies plugins before loading.

    Each ``verify_*`` method returns a list of error messages (empty
    when valid). The :meth:`verify` method runs all checks and returns
    a combined result dictionary with a ``valid`` flag and detailed
    error lists.

    Signature verification is currently a stub that always succeeds;
    this is reserved for future cryptographic verification of signed
    plugin packages.
    """

    def __init__(self, validator: Optional[LoaderValidator] = None) -> None:
        self._validator = validator or LoaderValidator()
        self._verified_count: int = 0
        self._passed_count: int = 0
        self._failed_count: int = 0

    def verify(
        self,
        manifest: PluginManifest,
        plugin_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run all verification checks and return a combined result.

        Args:
            manifest: The plugin manifest to verify.
            plugin_dir: Optional path to the plugin directory. When
                provided, the verifier checks that the path exists.

        Returns:
            A dictionary with:

            - ``valid`` (bool): Overall pass/fail.
            - ``plugin_id`` (str): The plugin identifier.
            - ``manifest_errors`` (list): Manifest validation errors.
            - ``entrypoint_errors`` (list): Entrypoint format errors.
            - ``compatibility_errors`` (list): API version errors.
            - ``dependency_errors`` (list): Missing dependency errors.
            - ``permission_errors`` (list): Permission declaration errors.
            - ``signature_errors`` (list): Signature verification errors.
            - ``errors`` (list): All errors combined.
            - ``warnings`` (list): Non-fatal warnings.
        """
        self._verified_count += 1

        plugin_id = getattr(manifest, "id", "") if manifest else ""

        manifest_errors = self.verify_manifest(manifest)
        entrypoint_errors = self.verify_entrypoint(manifest)
        compatibility_errors = self.verify_compatibility(manifest)
        dependency_errors = self.verify_dependencies(manifest)
        permission_errors = self.verify_permissions(manifest)
        signature_errors = self.verify_signature(manifest)

        errors: List[str] = []
        errors.extend(manifest_errors)
        errors.extend(entrypoint_errors)
        errors.extend(compatibility_errors)
        errors.extend(dependency_errors)
        errors.extend(permission_errors)
        errors.extend(signature_errors)

        warnings: List[str] = []
        if plugin_dir and not os.path.exists(plugin_dir):
            warnings.append(
                f"Plugin directory does not exist: {plugin_dir}"
            )

        valid = len(errors) == 0
        if valid:
            self._passed_count += 1
        else:
            self._failed_count += 1
            logger.debug(
                "Verification failed for '%s': %s",
                plugin_id,
                errors,
            )

        return {
            "valid": valid,
            "plugin_id": plugin_id,
            "manifest_errors": manifest_errors,
            "entrypoint_errors": entrypoint_errors,
            "compatibility_errors": compatibility_errors,
            "dependency_errors": dependency_errors,
            "permission_errors": permission_errors,
            "signature_errors": signature_errors,
            "errors": errors,
            "warnings": warnings,
        }

    def verify_manifest(self, manifest: PluginManifest) -> List[str]:
        """Verify the manifest is structurally valid.

        Args:
            manifest: The manifest to verify.

        Returns:
            A list of error messages; empty when valid.
        """
        if manifest is None:
            return ["Manifest is None"]

        return self._validator.validate_manifest(manifest)

    def verify_entrypoint(self, manifest: PluginManifest) -> List[str]:
        """Verify the plugin's entrypoint is well-formed.

        Args:
            manifest: The plugin manifest whose entrypoint to verify.

        Returns:
            A list of error messages; empty when valid.
        """
        if manifest is None:
            return ["Manifest is None"]

        entrypoint = manifest.entrypoint or ""
        return self._validator.validate_entrypoint(entrypoint)

    def verify_compatibility(
        self,
        manifest: PluginManifest,
        api_version: str = "v1",
    ) -> List[str]:
        """Verify the manifest targets a compatible API version.

        Args:
            manifest: The manifest to verify.
            api_version: The API version to check against.

        Returns:
            A list of error messages; empty when compatible.
        """
        errors: List[str] = []
        if manifest is None:
            errors.append("Manifest is None")
            return errors

        try:
            if not manifest.is_compatible(api_version):
                errors.append(
                    f"Plugin '{manifest.id}' is not compatible with "
                    f"API version '{api_version}'"
                )
        except Exception as exc:
            errors.append(f"Compatibility check failed: {exc}")

        return errors

    def verify_dependencies(
        self,
        manifest: PluginManifest,
        available: Optional[Set[str]] = None,
    ) -> List[str]:
        """Verify all required dependencies are available.

        Args:
            manifest: The plugin manifest whose dependencies to check.
            available: Set of available plugin ids. When ``None``,
                only structural validation is performed.

        Returns:
            A list of error messages; empty when all dependencies
            are satisfied.
        """
        errors: List[str] = []
        if manifest is None:
            errors.append("Manifest is None")
            return errors

        deps = manifest.dependencies or []
        if not deps:
            return errors

        available_set = available if available is not None else set()

        for dep in deps:
            if not isinstance(dep, str) or not dep:
                errors.append(f"Invalid dependency entry: {dep!r}")
                continue
            dep_name = dep.strip()
            if dep_name.startswith("?"):
                continue
            if not dep_name:
                errors.append(f"Invalid dependency entry: {dep!r}")
                continue
            if available is not None and dep_name not in available_set:
                errors.append(
                    f"Required dependency '{dep_name}' is not available"
                )

        return errors

    def verify_permissions(self, manifest: PluginManifest) -> List[str]:
        """Verify the permission declarations in a manifest.

        Args:
            manifest: The plugin manifest whose permissions to verify.

        Returns:
            A list of error messages; empty when permissions are
            well-formed.
        """
        errors: List[str] = []
        if manifest is None:
            errors.append("Manifest is None")
            return errors

        perms = manifest.permissions or []
        if not isinstance(perms, list):
            errors.append("Permissions must be a list")
            return errors

        for perm in perms:
            if not isinstance(perm, str) or not perm:
                errors.append(f"Invalid permission value: {perm!r}")

        return errors

    def verify_signature(self, manifest: PluginManifest) -> List[str]:
        """Verify the plugin's cryptographic signature.

        Currently a stub that always returns an empty list. Reserved
        for future cryptographic signature verification of signed
        plugin packages.

        Args:
            manifest: The plugin manifest whose signature to verify.

        Returns:
            An empty list (always succeeds for now).
        """
        return []

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the verifier state to a dictionary.

        Returns:
            A dictionary with verification counts and pass rate.
        """
        total = self._passed_count + self._failed_count
        return {
            "verified_count": self._verified_count,
            "passed_count": self._passed_count,
            "failed_count": self._failed_count,
            "pass_rate": (
                self._passed_count / total if total > 0 else 0.0
            ),
        }