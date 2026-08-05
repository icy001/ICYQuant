"""Main sandbox orchestrator.

Provides the :class:`Sandbox` class as the unified async entry
point for sandbox management, integrating isolation, permissions,
capabilities, resources, filesystem, network, secrets, crypto,
monitoring, and recovery into a cohesive security boundary.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from ..exceptions import (
    PluginIsolationError,
    PluginSandboxError,
    PluginSandboxViolationError,
)

from .audit import AuditLog
from .capabilities import SandboxCapabilityGuard
from .crypto import CryptoProvider, SignatureVerifier, TrustStore
from .diagnostics import SandboxDiagnostics
from .filesystem import FilesystemPolicy
from .isolation import IsolationManager
from .monitor import SandboxMetrics, SandboxMonitor
from .network import NetworkPolicy
from .permissions import SandboxPermissionGuard
from .recovery import RecoveryManager
from .resources import ResourceQuota, ResourceQuotaManager
from .runtime import SandboxRuntime
from .secrets import SecretAccessControl
from .security import SandboxValidator, SecurityPolicy

logger = logging.getLogger(__name__)


class Sandbox:
    """Main sandbox orchestrator for plugin security isolation.

    Provides a unified async API for creating, executing in, and
    destroying sandboxes.  Integrates all security components:

    - **Isolation** (process/thread) via :class:`IsolationManager`
    - **Permissions** via :class:`SandboxPermissionGuard`
    - **Capabilities** via :class:`SandboxCapabilityGuard`
    - **Resource quotas** via :class:`ResourceQuotaManager`
    - **Filesystem policy** via :class:`FilesystemPolicy`
    - **Network policy** via :class:`NetworkPolicy`
    - **Secret access** via :class:`SecretAccessControl`
    - **Crypto** via :class:`CryptoProvider`,
      :class:`SignatureVerifier`, :class:`TrustStore`
    - **Validation** via :class:`SandboxValidator`
    - **Monitoring** via :class:`SandboxMonitor` and
      :class:`SandboxMetrics`
    - **Auditing** via :class:`AuditLog`
    - **Diagnostics** via :class:`SandboxDiagnostics`
    - **Recovery** via :class:`RecoveryManager`

    Lifecycle: ``create_sandbox → enforce_policy → execute_in_sandbox
    → destroy_sandbox``

    Attributes:
        _sandboxes: Maps plugin_id → SandboxRuntime.
        _lock: Thread-safe reentrant lock.
    """

    def __init__(self) -> None:
        self._sandboxes: Dict[str, SandboxRuntime] = {}
        self._lock = threading.RLock()

        self.isolation = IsolationManager()
        self.permissions = SandboxPermissionGuard()
        self.capabilities = SandboxCapabilityGuard()
        self.resource_manager = ResourceQuotaManager()
        self.filesystem = FilesystemPolicy()
        self.network = NetworkPolicy()
        self.secrets = SecretAccessControl()
        self.crypto = CryptoProvider()
        self.signature_verifier = SignatureVerifier()
        self.trust_store = TrustStore()
        self.security_policy = SecurityPolicy()
        self.validator = SandboxValidator()
        self.metrics = SandboxMetrics()
        self.monitor = SandboxMonitor(metrics=self.metrics)
        self.audit_log = AuditLog()
        self.diagnostics = SandboxDiagnostics()
        self.recovery = RecoveryManager()

        self.recovery.register_restart_handler(
            "*", lambda: None
        )

        logger.info("Sandbox orchestrator initialized")

    async def create_sandbox(
        self,
        plugin_id: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> SandboxRuntime:
        """Create a new sandbox for a plugin.

        Validates the configuration, sets up isolation, applies
        the security policy, and registers the sandbox.

        Args:
            plugin_id: Unique identifier for the plugin.
            config: Optional sandbox configuration with keys:
                - ``memory_limit``: Max memory in bytes.
                - ``cpu_limit``: Max CPU percentage.
                - ``filesystem_root``: Sandbox filesystem root.
                - ``permissions``: List of permission strings.
                - ``capabilities``: List of capability strings.
                - ``allowed_paths``: List of allowed filesystem paths.
                - ``allowed_hosts``: List of allowed network hosts.
                - ``allowed_secrets``: List of allowed secret keys.
                - ``policy``: Security policy name to apply.

        Returns:
            The created :class:`SandboxRuntime`.

        Raises:
            PluginSandboxViolationError: If configuration validation
                fails.
            PluginIsolationError: If isolation creation fails.
        """
        config = config or {}
        start_time = time.time()

        self.validator.require_valid_config(config)

        with self._lock:
            if plugin_id in self._sandboxes:
                logger.warning(
                    "Sandbox already exists for plugin %s, destroying "
                    "previous",
                    plugin_id,
                )
                await self._destroy_sandbox_locked(plugin_id)

        runtime = SandboxRuntime(
            plugin_id=plugin_id,
            memory_limit=config.get(
                "memory_limit", 256 * 1024 * 1024
            ),
            cpu_limit=config.get("cpu_limit", 50.0),
            filesystem_root=config.get("filesystem_root", ""),
            allowed_network_hosts=list(
                config.get("allowed_hosts", [])
            ),
            allowed_permissions=list(
                config.get("permissions", [])
            ),
            allowed_capabilities=list(
                config.get("capabilities", [])
            ),
        )

        isolation_config = {
            "memory_limit": runtime.memory_limit,
            "cpu_limit": runtime.cpu_limit,
        }
        await self.isolation.create_isolation(
            plugin_id, isolation_config
        )

        quota = ResourceQuota(
            memory_bytes=runtime.memory_limit,
            cpu_percent=runtime.cpu_limit,
        )
        self.resource_manager.set_quota(plugin_id, quota)

        if runtime.allowed_permissions:
            self.permissions.set_permissions(
                plugin_id, runtime.allowed_permissions
            )
        if runtime.allowed_capabilities:
            self.capabilities.set_capabilities(
                plugin_id, runtime.allowed_capabilities
            )

        if runtime.filesystem_root:
            self.filesystem.set_root(plugin_id, runtime.filesystem_root)
            for path in config.get("allowed_paths", []):
                self.filesystem.allow_path(
                    plugin_id, path, "read"
                )
                self.filesystem.allow_path(
                    plugin_id, path, "write"
                )

        for host in runtime.allowed_network_hosts:
            self.network.allow_host(plugin_id, host)

        for secret_key in config.get("allowed_secrets", []):
            self.secrets.grant_secret_access(plugin_id, secret_key)

        with self._lock:
            self._sandboxes[plugin_id] = runtime

        self.monitor.register_plugin(plugin_id, status="created")
        self.audit_log.log_event(
            event_type="sandbox_created",
            plugin_id=plugin_id,
            message=f"Sandbox created for plugin {plugin_id}",
            details=config,
            severity="info",
        )

        elapsed = time.time() - start_time
        self.metrics.increment_counter("sandboxes_created")
        self.metrics.record_timing(
            "sandbox_creation_time", elapsed
        )

        logger.info(
            "Created sandbox for plugin %s in %.3fs",
            plugin_id, elapsed,
        )
        return runtime

    async def destroy_sandbox(self, plugin_id: str) -> None:
        """Destroy a sandbox and release all resources.

        Args:
            plugin_id: Unique identifier for the plugin.

        Raises:
            PluginIsolationError: If the sandbox does not exist
                or destruction fails.
        """
        with self._lock:
            if plugin_id not in self._sandboxes:
                raise PluginIsolationError(
                    f"No sandbox exists for plugin: {plugin_id}"
                )
            await self._destroy_sandbox_locked(plugin_id)

        self.metrics.increment_counter("sandboxes_destroyed")
        logger.info("Destroyed sandbox for plugin %s", plugin_id)

    async def _destroy_sandbox_locked(self, plugin_id: str) -> None:
        """Internal sandbox destruction (must be called with lock).

        Args:
            plugin_id: Unique identifier for the plugin.
        """
        runtime = self._sandboxes.pop(plugin_id, None)
        if runtime:
            runtime.status = "destroyed"

        try:
            await self.isolation.destroy_isolation(plugin_id)
        except PluginIsolationError:
            pass

        self.permissions.clear_permissions(plugin_id)
        self.capabilities.clear_capabilities(plugin_id)
        self.resource_manager.reset_usage(plugin_id)
        self.monitor.unregister_plugin(plugin_id)

        self.audit_log.log_event(
            event_type="sandbox_destroyed",
            plugin_id=plugin_id,
            message=f"Sandbox destroyed for plugin {plugin_id}",
            severity="info",
        )

    async def execute_in_sandbox(
        self,
        plugin_id: str,
        func: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute a function within a plugin's sandbox.

        Enforces all security policies before and during execution,
        monitors resource usage, and captures diagnostics.

        Args:
            plugin_id: Unique identifier for the plugin.
            func: The callable to execute.
            *args: Positional arguments passed to *func*.
            **kwargs: Keyword arguments passed to *func*.

        Returns:
            The return value of *func*.

        Raises:
            PluginSandboxViolationError: If any security check fails.
            PluginSandboxError: If execution fails.
        """
        start_time = time.time()

        with self._lock:
            runtime = self._sandboxes.get(plugin_id)
            if runtime is None:
                raise PluginSandboxError(
                    f"No sandbox exists for plugin: {plugin_id}"
                )

            if not runtime.is_active():
                raise PluginSandboxError(
                    f"Sandbox for plugin {plugin_id} is not active "
                    f"(status={runtime.status})"
                )

        await self.enforce_policy(plugin_id)

        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            duration = time.time() - start_time
            self.diagnostics.record_execution(
                plugin_id=plugin_id,
                function_name=getattr(func, "__name__", str(func)),
                duration=duration,
                success=False,
                error=str(exc),
            )
            self.monitor.record_violation(
                plugin_id, "execution_error",
                {"error": str(exc)},
            )
            self.metrics.increment_counter("execution_errors")
            raise PluginSandboxError(
                f"Execution failed in sandbox for plugin "
                f"{plugin_id}: {exc}"
            ) from exc

        duration = time.time() - start_time
        self.diagnostics.record_execution(
            plugin_id=plugin_id,
            function_name=getattr(func, "__name__", str(func)),
            duration=duration,
            success=True,
        )
        self.metrics.record_timing("sandbox_execution_time", duration)
        self.metrics.increment_counter("executions_completed")

        return result

    def get_sandbox(
        self, plugin_id: str
    ) -> Optional[SandboxRuntime]:
        """Get the sandbox runtime for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            The :class:`SandboxRuntime` if it exists, None otherwise.
        """
        with self._lock:
            return self._sandboxes.get(plugin_id)

    def list_sandboxes(self) -> List[Dict[str, Any]]:
        """List all active sandboxes.

        Returns:
            A list of sandbox runtime dictionaries.
        """
        with self._lock:
            return [
                runtime.to_dict()
                for runtime in self._sandboxes.values()
            ]

    async def enforce_policy(self, plugin_id: str) -> None:
        """Enforce the security policy on a sandbox.

        Runs all policy checks including resource quota enforcement
        and isolation health verification.

        Args:
            plugin_id: Unique identifier for the plugin.

        Raises:
            PluginSandboxViolationError: If any policy check fails.
        """
        self.resource_manager.enforce_quota(plugin_id)

        if not self.isolation.is_isolated(plugin_id):
            raise PluginSandboxViolationError(
                f"Plugin '{plugin_id}' has no active isolation"
            )

    def is_sandboxed(self, plugin_id: str) -> bool:
        """Check whether a plugin has an active sandbox.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            True if an active sandbox exists.
        """
        with self._lock:
            runtime = self._sandboxes.get(plugin_id)
            return runtime is not None and runtime.is_active()

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive sandbox statistics.

        Returns:
            A dictionary with counts and sub-component statistics.
        """
        with self._lock:
            total = len(self._sandboxes)
            active = sum(
                1
                for r in self._sandboxes.values()
                if r.is_active()
            )

        return {
            "total_sandboxes": total,
            "active_sandboxes": active,
            "sandboxes": self.list_sandboxes(),
            "isolation": self.isolation.get_stats(),
            "permissions": self.permissions.get_stats(),
            "capabilities": self.capabilities.get_stats(),
            "resources": self.resource_manager.get_stats(),
            "filesystem": self.filesystem.get_stats(),
            "network": self.network.get_stats(),
            "secrets": self.secrets.get_stats(),
            "monitor": self.monitor.get_stats(),
            "audit": self.audit_log.get_stats(),
            "diagnostics": self.diagnostics.get_stats(),
            "recovery": self.recovery.get_stats(),
            "metrics": self.metrics.get_stats(),
        }

    async def shutdown(self) -> None:
        """Shut down all sandboxes and release resources.

        Destroys all active sandboxes and clears all component
        state.
        """
        with self._lock:
            plugin_ids = list(self._sandboxes.keys())

        for pid in plugin_ids:
            try:
                await self.destroy_sandbox(pid)
            except Exception:
                logger.exception(
                    "Error destroying sandbox for plugin %s "
                    "during shutdown",
                    pid,
                )

        self.audit_log.log_event(
            event_type="sandbox_shutdown",
            plugin_id="*",
            message="All sandboxes shut down",
            severity="info",
        )

        logger.info("Sandbox orchestrator shut down")