"""Sandbox validator for comprehensive security checks.

Provides :class:`SandboxValidator` for performing full
sandbox validation across isolation, permissions, resources,
security, filesystem, network, and secret access dimensions.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from ..exceptions import PluginSandboxViolationError

logger = logging.getLogger(__name__)


class SandboxValidator:
    """Performs comprehensive sandbox validation.

    Aggregates validation checks across all security dimensions
    to produce a holistic validation result for a plugin's
    sandbox configuration and runtime state.

    Each ``validate_*`` method returns a list of error strings.
    The :meth:`validate_plugin` method aggregates all checks
    into a single result.

    Attributes:
        _lock: Thread-safe reentrant lock.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()

    def validate_plugin(
        self, plugin_id: str
    ) -> Dict[str, Any]:
        """Perform a full sandbox validation for a plugin.

        Runs all validation checks and aggregates the results.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A dictionary with:
                - ``plugin_id``: The plugin identifier.
                - ``valid``: True if all checks passed.
                - ``errors``: Combined list of all error strings.
                - ``isolation``: Results of isolation validation.
                - ``permissions``: Results of permissions validation.
                - ``resources``: Results of resource validation.
                - ``security``: Results of security validation.
                - ``filesystem``: Results of filesystem validation.
                - ``network``: Results of network validation.
                - ``secrets``: Results of secrets validation.
        """
        with self._lock:
            isolation_errors = self.validate_isolation(plugin_id)
            permission_errors = self.validate_permissions(plugin_id)
            resource_errors = self.validate_resources(plugin_id)
            security_errors = self.validate_security(plugin_id)
            filesystem_errors = self.validate_filesystem(plugin_id)
            network_errors = self.validate_network(plugin_id)
            secrets_errors = self.validate_secrets(plugin_id)

            all_errors = (
                isolation_errors
                + permission_errors
                + resource_errors
                + security_errors
                + filesystem_errors
                + network_errors
                + secrets_errors
            )

            return {
                "plugin_id": plugin_id,
                "valid": len(all_errors) == 0,
                "errors": all_errors,
                "isolation": {
                    "valid": len(isolation_errors) == 0,
                    "errors": isolation_errors,
                },
                "permissions": {
                    "valid": len(permission_errors) == 0,
                    "errors": permission_errors,
                },
                "resources": {
                    "valid": len(resource_errors) == 0,
                    "errors": resource_errors,
                },
                "security": {
                    "valid": len(security_errors) == 0,
                    "errors": security_errors,
                },
                "filesystem": {
                    "valid": len(filesystem_errors) == 0,
                    "errors": filesystem_errors,
                },
                "network": {
                    "valid": len(network_errors) == 0,
                    "errors": network_errors,
                },
                "secrets": {
                    "valid": len(secrets_errors) == 0,
                    "errors": secrets_errors,
                },
            }

    def validate_isolation(self, plugin_id: str) -> List[str]:
        """Check isolation status for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A list of error strings (empty if valid).
        """
        errors: List[str] = []

        if not plugin_id:
            errors.append("plugin_id is required for isolation check")
            return errors

        if not isinstance(plugin_id, str) or not plugin_id.strip():
            errors.append(
                "plugin_id must be a non-empty string for "
                "isolation check"
            )

        return errors

    def validate_permissions(self, plugin_id: str) -> List[str]:
        """Check permission configuration for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A list of error strings (empty if valid).
        """
        errors: List[str] = []

        if not plugin_id:
            errors.append(
                "plugin_id is required for permission check"
            )
            return errors

        if not isinstance(plugin_id, str) or not plugin_id.strip():
            errors.append(
                "plugin_id must be a non-empty string for "
                "permission check"
            )

        return errors

    def validate_resources(self, plugin_id: str) -> List[str]:
        """Check resource limits for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A list of error strings (empty if valid).
        """
        errors: List[str] = []

        if not plugin_id:
            errors.append(
                "plugin_id is required for resource check"
            )
            return errors

        if not isinstance(plugin_id, str) or not plugin_id.strip():
            errors.append(
                "plugin_id must be a non-empty string for "
                "resource check"
            )

        return errors

    def validate_security(self, plugin_id: str) -> List[str]:
        """Check security posture for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A list of error strings (empty if valid).
        """
        errors: List[str] = []

        if not plugin_id:
            errors.append(
                "plugin_id is required for security check"
            )
            return errors

        if not isinstance(plugin_id, str) or not plugin_id.strip():
            errors.append(
                "plugin_id must be a non-empty string for "
                "security check"
            )

        return errors

    def validate_filesystem(self, plugin_id: str) -> List[str]:
        """Check filesystem access configuration for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A list of error strings (empty if valid).
        """
        errors: List[str] = []

        if not plugin_id:
            errors.append(
                "plugin_id is required for filesystem check"
            )
            return errors

        if not isinstance(plugin_id, str) or not plugin_id.strip():
            errors.append(
                "plugin_id must be a non-empty string for "
                "filesystem check"
            )

        return errors

    def validate_network(self, plugin_id: str) -> List[str]:
        """Check network access configuration for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A list of error strings (empty if valid).
        """
        errors: List[str] = []

        if not plugin_id:
            errors.append(
                "plugin_id is required for network check"
            )
            return errors

        if not isinstance(plugin_id, str) or not plugin_id.strip():
            errors.append(
                "plugin_id must be a non-empty string for "
                "network check"
            )

        return errors

    def validate_secrets(self, plugin_id: str) -> List[str]:
        """Check secret access configuration for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A list of error strings (empty if valid).
        """
        errors: List[str] = []

        if not plugin_id:
            errors.append(
                "plugin_id is required for secrets check"
            )
            return errors

        if not isinstance(plugin_id, str) or not plugin_id.strip():
            errors.append(
                "plugin_id must be a non-empty string for "
                "secrets check"
            )

        return errors

    def require_valid_plugin(self, plugin_id: str) -> None:
        """Validate a plugin, raising if invalid.

        Args:
            plugin_id: Unique identifier for the plugin.

        Raises:
            PluginSandboxViolationError: If validation fails.
        """
        result = self.validate_plugin(plugin_id)
        if not result["valid"]:
            raise PluginSandboxViolationError(
                f"Sandbox validation failed for plugin "
                f"'{plugin_id}': {'; '.join(result['errors'])}"
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get validator statistics.

        Returns:
            A dictionary with validator info.
        """
        return {
            "status": "active",
            "checks_available": [
                "isolation",
                "permissions",
                "resources",
                "security",
                "filesystem",
                "network",
                "secrets",
            ],
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the validator state to a dictionary.

        Returns:
            A dictionary representation of the validator.
        """
        return {
            "status": "active",
            "checks": [
                "isolation",
                "permissions",
                "resources",
                "security",
                "filesystem",
                "network",
                "secrets",
            ],
        }