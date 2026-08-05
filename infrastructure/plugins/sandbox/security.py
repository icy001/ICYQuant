"""Security policy and sandbox validation.

Provides :class:`SecurityPolicy` for defining comprehensive
security rules and :class:`SandboxValidator` for validating
sandbox configurations before execution.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from ..exceptions import PluginSandboxError, PluginSandboxViolationError

logger = logging.getLogger(__name__)


class SecurityPolicy:
    """Defines and manages security policies for sandboxed plugins.

    A security policy aggregates permissions, capabilities,
    filesystem rules, and network rules into a single named
    policy that can be applied to plugins.

    Attributes:
        _policies: Maps policy_name to its configuration dictionary.
        _lock: Thread-safe reentrant lock.
    """

    def __init__(self) -> None:
        self._policies: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def define_policy(
        self,
        name: str,
        permissions: Optional[List[str]] = None,
        capabilities: Optional[List[str]] = None,
        allowed_paths: Optional[List[str]] = None,
        allowed_hosts: Optional[List[str]] = None,
        allowed_secrets: Optional[List[str]] = None,
        resource_quota: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Define a named security policy.

        Args:
            name: Unique policy name.
            permissions: Permission strings to grant.
            capabilities: Capability strings to grant.
            allowed_paths: Filesystem paths to allow.
            allowed_hosts: Network hosts to allow.
            allowed_secrets: Secret keys to allow.
            resource_quota: Resource quota configuration.
        """
        with self._lock:
            self._policies[name] = {
                "permissions": list(permissions or []),
                "capabilities": list(capabilities or []),
                "allowed_paths": list(allowed_paths or []),
                "allowed_hosts": list(allowed_hosts or []),
                "allowed_secrets": list(allowed_secrets or []),
                "resource_quota": dict(resource_quota or {}),
            }
            logger.info("Defined security policy: %s", name)

    def get_policy(self, name: str) -> Dict[str, Any]:
        """Get a security policy by name.

        Args:
            name: The policy name.

        Returns:
            The policy configuration dictionary.

        Raises:
            PluginSandboxError: If the policy is not found.
        """
        with self._lock:
            if name not in self._policies:
                raise PluginSandboxError(
                    f"Security policy not found: {name}"
                )
            return dict(self._policies[name])

    def delete_policy(self, name: str) -> None:
        """Delete a security policy.

        Args:
            name: The policy name.
        """
        with self._lock:
            self._policies.pop(name, None)
            logger.info("Deleted security policy: %s", name)

    def list_policies(self) -> List[str]:
        """List all defined policy names.

        Returns:
            A sorted list of policy names.
        """
        with self._lock:
            return sorted(self._policies.keys())

    def get_stats(self) -> Dict[str, Any]:
        """Get security policy statistics.

        Returns:
            A dictionary with total policy count and policy names.
        """
        with self._lock:
            return {
                "total_policies": len(self._policies),
                "policies": sorted(self._policies.keys()),
            }


class SandboxValidator:
    """Validates sandbox configurations and policy compliance.

    Checks sandbox configurations before execution to ensure
    they meet security requirements and do not contain
    contradictory or dangerous settings.

    Attributes:
        _lock: Thread-safe reentrant lock.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()

    def validate_config(
        self, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate a sandbox configuration dictionary.

        Args:
            config: The sandbox configuration to validate.

        Returns:
            A dictionary with ``valid`` (bool), ``errors`` (list of
            error strings), and ``warnings`` (list of warning strings).
        """
        errors: List[str] = []
        warnings: List[str] = []

        if not isinstance(config, dict):
            errors.append("Configuration must be a dictionary")
            return {
                "valid": False,
                "errors": errors,
                "warnings": warnings,
            }

        plugin_id = config.get("plugin_id")
        if not plugin_id:
            errors.append("plugin_id is required")

        memory_limit = config.get("memory_limit")
        if memory_limit is not None and (
            not isinstance(memory_limit, int) or memory_limit <= 0
        ):
            errors.append(
                f"memory_limit must be a positive integer, got: {memory_limit}"
            )

        cpu_limit = config.get("cpu_limit")
        if cpu_limit is not None and (
            not isinstance(cpu_limit, (int, float))
            or cpu_limit <= 0
            or cpu_limit > 100
        ):
            errors.append(
                f"cpu_limit must be between 0 and 100, got: {cpu_limit}"
            )

        filesystem_root = config.get("filesystem_root")
        if filesystem_root is not None and not isinstance(
            filesystem_root, str
        ):
            errors.append("filesystem_root must be a string")

        if errors:
            logger.warning(
                "Sandbox validation failed with %d errors", len(errors)
            )
        else:
            logger.debug("Sandbox configuration validated successfully")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def require_valid_config(self, config: Dict[str, Any]) -> None:
        """Validate a configuration, raising if invalid.

        Args:
            config: The sandbox configuration to validate.

        Raises:
            PluginSandboxViolationError: If validation fails.
        """
        result = self.validate_config(config)
        if not result["valid"]:
            raise PluginSandboxViolationError(
                f"Sandbox configuration validation failed: "
                f"{'; '.join(result['errors'])}"
            )

    def validate_policy_compliance(
        self,
        plugin_id: str,
        policy: Dict[str, Any],
        runtime_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Validate that a runtime configuration complies with a policy.

        Args:
            plugin_id: The plugin identifier.
            policy: The security policy configuration.
            runtime_config: The actual runtime configuration.

        Returns:
            A dictionary with ``compliant`` (bool) and ``violations``.
        """
        violations: List[str] = []

        policy_memory = policy.get("resource_quota", {}).get(
            "memory_bytes"
        )
        runtime_memory = runtime_config.get("memory_limit")
        if policy_memory and runtime_memory:
            if runtime_memory > policy_memory:
                violations.append(
                    f"memory_limit ({runtime_memory}) exceeds policy "
                    f"maximum ({policy_memory})"
                )

        policy_cpu = policy.get("resource_quota", {}).get(
            "cpu_percent"
        )
        runtime_cpu = runtime_config.get("cpu_limit")
        if policy_cpu and runtime_cpu:
            if runtime_cpu > policy_cpu:
                violations.append(
                    f"cpu_limit ({runtime_cpu}) exceeds policy "
                    f"maximum ({policy_cpu})"
                )

        return {
            "plugin_id": plugin_id,
            "compliant": len(violations) == 0,
            "violations": violations,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get validator statistics.

        Returns:
            A dictionary with validator info.
        """
        return {
            "status": "active",
        }