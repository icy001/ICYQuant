"""
Secrets platform bootstrap.

Provides the unified initialization sequence for
the entire secrets platform, orchestrating
component startup and shutdown in the correct
dependency order.

Startup Order:
    Secrets Manager
        ↓
    Vault Provider
        ↓
    Cache
        ↓
    Rotation Engine
        ↓
    Policy
        ↓
    Permissions
        ↓
    Audit
        ↓
    Metrics
        ↓
    Health Check
        ↓
    Telemetry

Shutdown Order:
    Stop Rotation Scheduler
        ↓
    Flush Audit
        ↓
    Clear Cache
        ↓
    Shutdown Providers
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import SecretsConfig

logger = logging.getLogger(__name__)


class SecretsBootstrap:
    """
    Secrets platform bootstrap.

    Orchestrates the full startup sequence for the
    secrets platform, ensuring correct
    initialization order and dependency resolution.

    Usage:
        bootstrap = SecretsBootstrap()
        result = await bootstrap.startup()
        # ... platform running ...
        await bootstrap.shutdown()
    """

    def __init__(
        self,
        config: Optional[SecretsConfig] = None,
        enable_scheduler: bool = True,
        enable_metrics: bool = True,
        enable_audit: bool = True,
    ) -> None:
        """
        Initialize bootstrap.

        Args:
            config: Secrets configuration.
            enable_scheduler: Enable background rotation scheduler.
            enable_metrics: Enable metrics collection.
            enable_audit: Enable audit logging.
        """
        self._config = config or SecretsConfig()
        self._enable_scheduler = enable_scheduler
        self._enable_metrics = enable_metrics
        self._enable_audit = enable_audit

        self._components: Dict[str, Any] = {}
        self._startup_log: List[Dict[str, Any]] = []
        self._started = False

        self._manager: Optional[Any] = None
        self._vault_provider: Optional[Any] = None
        self._cache: Optional[Any] = None
        self._rotation_manager: Optional[Any] = None
        self._policy: Optional[Any] = None
        self._permissions: Optional[Any] = None
        self._audit: Optional[Any] = None
        self._metrics: Optional[Any] = None
        self._health_check: Optional[Any] = None
        self._telemetry: Optional[Any] = None
        self._scheduler: Optional[Any] = None

    @property
    def config(self) -> SecretsConfig:
        """Get secrets configuration."""
        return self._config

    @property
    def manager(self) -> Optional[Any]:
        """Get secrets manager."""
        return self._manager

    @property
    def vault_provider(self) -> Optional[Any]:
        """Get vault provider."""
        return self._vault_provider

    @property
    def cache(self) -> Optional[Any]:
        """Get secrets cache."""
        return self._cache

    @property
    def rotation_manager(self) -> Optional[Any]:
        """Get rotation manager."""
        return self._rotation_manager

    @property
    def policy(self) -> Optional[Any]:
        """Get access policy."""
        return self._policy

    @property
    def permissions(self) -> Optional[Any]:
        """Get permission model."""
        return self._permissions

    @property
    def audit(self) -> Optional[Any]:
        """Get audit logger."""
        return self._audit

    @property
    def metrics(self) -> Optional[Any]:
        """Get metrics collector."""
        return self._metrics

    @property
    def health_check(self) -> Optional[Any]:
        """Get health checker."""
        return self._health_check

    @property
    def telemetry(self) -> Optional[Any]:
        """Get telemetry handler."""
        return self._telemetry

    @property
    def scheduler(self) -> Optional[Any]:
        """Get rotation scheduler."""
        return self._scheduler

    @property
    def startup_log(self) -> List[Dict[str, Any]]:
        """Get startup log."""
        return list(self._startup_log)

    @property
    def is_started(self) -> bool:
        """Check if bootstrap is started."""
        return self._started

    async def startup(self) -> Dict[str, Any]:
        """
        Execute the full startup sequence.

        Returns:
            Startup result with component status.
        """
        self._startup_log.clear()

        await self._init_step(
            "secrets_manager", self._init_secrets_manager,
        )

        await self._init_step(
            "vault_provider", self._init_vault_provider,
        )

        await self._init_step(
            "cache", self._init_cache,
        )

        await self._init_step(
            "rotation_engine", self._init_rotation_engine,
        )

        await self._init_step(
            "policy", self._init_policy,
        )

        await self._init_step(
            "permissions", self._init_permissions,
        )

        if self._enable_audit:
            await self._init_step(
                "audit", self._init_audit,
            )

        if self._enable_metrics:
            await self._init_step(
                "metrics", self._init_metrics,
            )

        await self._init_step(
            "health_check", self._init_health_check,
        )

        await self._init_step(
            "telemetry", self._init_telemetry,
        )

        if self._enable_scheduler and self._rotation_manager is not None:
            await self._init_step(
                "scheduler", self._init_scheduler,
            )

        self._started = True

        result = await self._run_health_check()

        return {
            "success": True,
            "components": dict(self._components),
            "startup_log": self._startup_log,
            "health": result,
        }

    async def shutdown(
        self,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Shut down the secrets platform.

        Shutdown order:
        1. Stop rotation scheduler
        2. Flush audit
        3. Clear cache
        4. Shutdown providers

        Args:
            timeout: Shutdown timeout in seconds.

        Returns:
            Shutdown result.
        """
        shutdown_log: List[Dict[str, Any]] = []

        start = datetime.utcnow()
        try:
            if self._scheduler is not None:
                stop_result = self._scheduler.stop()
                if asyncio.iscoroutine(stop_result):
                    await asyncio.wait_for(
                        stop_result, timeout=timeout,
                    )
            shutdown_log.append({
                "step": "stop_rotation_scheduler",
                "status": "ok",
                "elapsed": (datetime.utcnow() - start).total_seconds(),
            })
        except Exception as e:
            shutdown_log.append({
                "step": "stop_rotation_scheduler",
                "status": "error",
                "error": str(e),
                "elapsed": (datetime.utcnow() - start).total_seconds(),
            })

        start = datetime.utcnow()
        try:
            if self._audit is not None:
                if hasattr(self._audit, 'flush'):
                    flush_result = self._audit.flush()
                    if asyncio.iscoroutine(flush_result):
                        await flush_result
                elif hasattr(self._audit, 'close'):
                    self._audit.close()
            shutdown_log.append({
                "step": "flush_audit",
                "status": "ok",
                "elapsed": (datetime.utcnow() - start).total_seconds(),
            })
        except Exception as e:
            shutdown_log.append({
                "step": "flush_audit",
                "status": "error",
                "error": str(e),
                "elapsed": (datetime.utcnow() - start).total_seconds(),
            })

        start = datetime.utcnow()
        try:
            if self._cache is not None:
                if hasattr(self._cache, 'clear'):
                    self._cache.clear()
            shutdown_log.append({
                "step": "clear_cache",
                "status": "ok",
                "elapsed": (datetime.utcnow() - start).total_seconds(),
            })
        except Exception as e:
            shutdown_log.append({
                "step": "clear_cache",
                "status": "error",
                "error": str(e),
                "elapsed": (datetime.utcnow() - start).total_seconds(),
            })

        start = datetime.utcnow()
        try:
            if self._vault_provider is not None:
                if hasattr(self._vault_provider, 'shutdown'):
                    shutdown_result = self._vault_provider.shutdown()
                    if asyncio.iscoroutine(shutdown_result):
                        await asyncio.wait_for(
                            shutdown_result, timeout=timeout,
                        )
            shutdown_log.append({
                "step": "shutdown_providers",
                "status": "ok",
                "elapsed": (datetime.utcnow() - start).total_seconds(),
            })
        except Exception as e:
            shutdown_log.append({
                "step": "shutdown_providers",
                "status": "error",
                "error": str(e),
                "elapsed": (datetime.utcnow() - start).total_seconds(),
            })

        self._components.clear()
        self._started = False

        return {
            "success": True,
            "shutdown_log": shutdown_log,
        }

    async def _init_step(
        self,
        name: str,
        init_func: Any,
    ) -> None:
        """Execute a single initialization step."""
        start = datetime.utcnow()
        try:
            result = init_func()
            if asyncio.iscoroutine(result):
                result = await result

            self._components[name] = result
            elapsed = (datetime.utcnow() - start).total_seconds()
            self._startup_log.append({
                "step": name,
                "status": "ok",
                "elapsed": elapsed,
            })
            logger.info(
                "Initialized %s in %.3fs", name, elapsed,
            )
        except Exception as e:
            elapsed = (datetime.utcnow() - start).total_seconds()
            self._startup_log.append({
                "step": name,
                "status": "error",
                "error": str(e),
                "elapsed": elapsed,
            })
            logger.error(
                "Failed to initialize %s: %s", name, e,
            )
            raise

    def _init_secrets_manager(self) -> Any:
        """Initialize secrets manager."""
        from .manager import SecretsManager

        self._manager = SecretsManager(
            config=self._config,
            provider=self._vault_provider if hasattr(self, '_vault_provider') else None,
            cache=self._cache if hasattr(self, '_cache') else None,
        )
        return self._manager

    async def _init_vault_provider(self) -> Any:
        """Initialize vault provider."""
        try:
            from .vault.provider import VaultSecretsProvider
            self._vault_provider = VaultSecretsProvider()
        except Exception:
            from .provider import LocalSecretsProvider
            self._vault_provider = LocalSecretsProvider()
        return self._vault_provider

    def _init_cache(self) -> Any:
        """Initialize secrets cache."""
        from .cache import SecretsCache

        self._cache = SecretsCache(
            ttl=self._config.cache_ttl,
            max_size=self._config.cache_max_size,
        )
        return self._cache

    def _init_rotation_engine(self) -> Any:
        """Initialize rotation engine."""
        from .rotation.manager import SecretRotationManager

        self._rotation_manager = SecretRotationManager()
        return self._rotation_manager

    def _init_policy(self) -> Any:
        """Initialize access policy."""
        from .policy import SecretAccessPolicy

        self._policy = SecretAccessPolicy()
        return self._policy

    def _init_permissions(self) -> Any:
        """Initialize permission model."""
        from .permissions import PermissionModel

        self._permissions = PermissionModel()
        return self._permissions

    def _init_audit(self) -> Any:
        """Initialize audit logger."""
        from .audit import SecretsAudit

        self._audit = SecretsAudit()
        return self._audit

    def _init_metrics(self) -> Any:
        """Initialize metrics collection."""
        from .metrics import SecretsMetrics

        self._metrics = SecretsMetrics(enabled=True)
        return self._metrics

    def _init_health_check(self) -> Any:
        """Initialize health check."""
        from .health import SecretsHealthCheck

        self._health_check = SecretsHealthCheck(
            manager=self._manager,
            provider=self._vault_provider,
            cache=self._cache,
        )
        return self._health_check

    def _init_telemetry(self) -> Any:
        """Initialize telemetry integration."""
        telemetry_info = {
            "manager": self._manager is not None,
            "provider": self._vault_provider is not None,
            "cache": self._cache is not None,
            "metrics": self._metrics is not None,
            "audit": self._audit is not None,
        }
        self._telemetry = telemetry_info
        return telemetry_info

    async def _init_scheduler(self) -> Any:
        """Initialize rotation scheduler."""
        from .rotation.scheduler import RotationScheduler

        self._scheduler = RotationScheduler()
        if hasattr(self._scheduler, 'start'):
            start_result = self._scheduler.start()
            if asyncio.iscoroutine(start_result):
                await start_result
        return self._scheduler

    async def _run_health_check(self) -> Dict[str, Any]:
        """Run initial health check after startup."""
        if self._health_check is not None:
            try:
                return await self._health_check.check_all()
            except Exception as e:
                logger.warning(
                    "Health check failed after startup: %s", e,
                )
                return {"healthy": False, "error": str(e)}
        return {"healthy": True}

    def get_status(self) -> Dict[str, Any]:
        """Get bootstrap status."""
        return {
            "started": self._started,
            "config": self._config.model_dump()
            if hasattr(self._config, 'model_dump')
            else self._config.to_dict()
            if hasattr(self._config, 'to_dict')
            else {},
            "components": list(self._components.keys()),
            "startup_steps": len(self._startup_log),
            "manager": (
                self._manager.get_status()
                if self._manager is not None
                and hasattr(self._manager, 'get_status')
                else None
            ),
            "rotation_manager": (
                self._rotation_manager.get_status()
                if self._rotation_manager is not None
                and hasattr(self._rotation_manager, 'get_status')
                else None
            ),
            "scheduler": (
                self._scheduler.get_status()
                if self._scheduler is not None
                and hasattr(self._scheduler, 'get_status')
                else None
            ),
            "health": (
                self._health_check.get_status()
                if self._health_check is not None
                and hasattr(self._health_check, 'get_status')
                else None
            ),
        }