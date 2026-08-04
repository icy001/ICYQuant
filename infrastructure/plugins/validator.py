"""Plugin validation.

Validates plugins before loading and during operation, checking
manifest validity, entrypoint accessibility, dependency
completeness, permission declarations, capability declarations,
and runtime health.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .capabilities import Capability
from .exceptions import PluginValidationError
from .permissions import Permission

logger = logging.getLogger(__name__)


class PluginValidator:
    """Validates plugins before loading and during operation.

    Checks:
    - Manifest validity
    - Entrypoint accessibility
    - Dependency completeness
    - Permission declarations
    - Capability declarations
    - Runtime health
    """

    def __init__(self) -> None:
        self._validation_count: int = 0
        self._error_count: int = 0
        self._last_errors: List[str] = []

    def validate_manifest(self, manifest: Any) -> List[str]:
        errors: List[str] = []
        if manifest is None:
            errors.append("Manifest is None")
            return errors
        if hasattr(manifest, "validate") and callable(manifest.validate):
            manifest_errors = manifest.validate()
            errors.extend(manifest_errors)
            return errors
        if hasattr(manifest, "id") and not manifest.id:
            errors.append("Manifest field 'id' is required")
        if hasattr(manifest, "name") and not manifest.name:
            errors.append("Manifest field 'name' is required")
        if hasattr(manifest, "version") and not manifest.version:
            errors.append("Manifest field 'version' is required")
        if hasattr(manifest, "entrypoint") and manifest.entrypoint == "":
            errors.append("Manifest field 'entrypoint' is required")
        if hasattr(manifest, "api") and not manifest.api:
            errors.append("Manifest field 'api' is required")
        return errors

    def validate_entrypoint(self, entrypoint: str) -> List[str]:
        errors: List[str] = []
        if not entrypoint or not isinstance(entrypoint, str):
            errors.append("Entrypoint must be a non-empty string")
            return errors
        if ":" in entrypoint:
            parts = entrypoint.split(":")
            if len(parts) != 2:
                errors.append(
                    f"Entrypoint format should be 'module:class', got: {entrypoint!r}"
                )
            else:
                module_path, class_name = parts
                if not module_path:
                    errors.append("Entrypoint module path cannot be empty")
                if not class_name:
                    errors.append("Entrypoint class name cannot be empty")
                if module_path and not self._is_valid_module_path(module_path):
                    errors.append(
                        f"Entrypoint module path '{module_path}' contains invalid characters"
                    )
                if class_name and not class_name.isidentifier():
                    errors.append(
                        f"Entrypoint class name '{class_name}' is not a valid identifier"
                    )
        else:
            if not self._is_valid_module_path(entrypoint):
                errors.append(
                    f"Entrypoint '{entrypoint}' contains invalid characters"
                )
        return errors

    def validate_dependencies(
        self, deps: List[str], available: List[str]
    ) -> List[str]:
        errors: List[str] = []
        if deps is None:
            return errors
        if not isinstance(deps, list):
            errors.append("Dependencies must be a list")
            return errors
        available_set = set(available) if available else set()
        for dep in deps:
            if not isinstance(dep, str) or not dep:
                errors.append(f"Invalid dependency entry: {dep!r}")
                continue
            dep_name = dep.strip()
            if dep_name.startswith("?"):
                optional_dep = dep_name[1:]
                if optional_dep and optional_dep not in available_set:
                    logger.debug(
                        "Optional dependency '%s' not found (non-fatal).", optional_dep
                    )
                continue
            if dep_name and dep_name not in available_set:
                errors.append(f"Required dependency '{dep_name}' is not available")
        return errors

    def validate_permissions(
        self, declared: List[str], granted: List[str]
    ) -> List[str]:
        errors: List[str] = []
        if declared is None:
            declared = []
        if granted is None:
            granted = []
        granted_set = set(granted)
        valid_permissions = {p.value for p in Permission}
        for perm in declared:
            if not isinstance(perm, str) or not perm:
                errors.append(f"Invalid permission value: {perm!r}")
                continue
            if perm not in valid_permissions:
                errors.append(f"Unknown permission: '{perm}'")
                continue
            if perm not in granted_set:
                errors.append(f"Permission '{perm}' is declared but not granted")
        return errors

    def validate_capabilities(self, caps: List[str]) -> List[str]:
        errors: List[str] = []
        if caps is None:
            return errors
        if not isinstance(caps, list):
            errors.append("Capabilities must be a list")
            return errors
        valid_caps = {c.value for c in Capability}
        for cap in caps:
            if not isinstance(cap, str) or not cap:
                errors.append(f"Invalid capability value: {cap!r}")
                continue
            if cap not in valid_caps:
                errors.append(f"Unknown capability: '{cap}'")
        return errors

    def validate_plugin(
        self,
        manifest: Any,
        deps: List[str],
        perms: List[str],
        caps: List[str],
    ) -> Dict[str, Any]:
        self._validation_count += 1
        all_errors: List[str] = []
        manifest_errors = self.validate_manifest(manifest)
        all_errors.extend(manifest_errors)
        entrypoint = ""
        if manifest is not None and hasattr(manifest, "entrypoint"):
            entrypoint = manifest.entrypoint or ""
        entrypoint_errors = self.validate_entrypoint(entrypoint)
        all_errors.extend(entrypoint_errors)
        dependency_errors = self.validate_dependencies(deps, [])
        all_errors.extend(dependency_errors)
        permission_errors = self.validate_permissions(perms, perms)
        all_errors.extend(permission_errors)
        capability_errors = self.validate_capabilities(caps)
        all_errors.extend(capability_errors)
        valid = len(all_errors) == 0
        if not valid:
            self._error_count += 1
        self._last_errors = all_errors
        result: Dict[str, Any] = {
            "valid": valid,
            "errors": all_errors,
            "manifest_errors": manifest_errors,
            "entrypoint_errors": entrypoint_errors,
            "dependency_errors": dependency_errors,
            "permission_errors": permission_errors,
            "capability_errors": capability_errors,
        }
        return result

    def get_stats(self) -> Dict[str, Any]:
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
    def _is_valid_module_path(path: str) -> bool:
        if not path:
            return False
        cleaned = path.replace(".", "").replace("_", "").replace("-", "")
        return cleaned.isalnum()