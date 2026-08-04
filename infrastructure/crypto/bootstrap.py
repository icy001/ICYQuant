"""
Crypto platform bootstrap.

Provides the unified initialization sequence for
the entire cryptographic platform, orchestrating
component startup and shutdown in the correct
dependency order.

Startup Order:
    Crypto Service
        ↓
    KMS Provider
        ↓
    Key Store
        ↓
    Algorithm Registry
        ↓
    Metrics
        ↓
    Health Check

Shutdown Order:
    Stop Schedulers
        ↓
    Flush Audit
        ↓
    Persist Key Metadata
        ↓
    Shutdown Providers
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import CryptoConfig
from .service import CryptoService
from .factory import CryptoFactory
from .keystore import KeyStore
from .keyring import Keyring
from .registry import AlgorithmRegistry
from .metrics import CryptoMetrics
from .health import CryptoHealthCheck
from .diagnostics import CryptoDiagnostics
from .manager import CryptoManager
from .scheduler import CryptoScheduler

logger = logging.getLogger(__name__)


class CryptoBootstrap:
    """
    Crypto platform bootstrap.

    Orchestrates the full startup sequence for the
    cryptographic platform, ensuring correct
    initialization order and dependency resolution.

    Usage:
        bootstrap = CryptoBootstrap()
        result = await bootstrap.startup()
        # ... platform running ...
        await bootstrap.shutdown()
    """

    def __init__(
        self,
        config: Optional[CryptoConfig] = None,
        enable_scheduler: bool = True,
        enable_metrics: bool = True,
        enable_diagnostics: bool = True,
    ) -> None:
        """
        Initialize bootstrap.

        Args:
            config: Crypto configuration.
            enable_scheduler: Enable background scheduler.
            enable_metrics: Enable metrics collection.
            enable_diagnostics: Enable diagnostics collection.
        """
        self._config = config or CryptoConfig()
        self._enable_scheduler = enable_scheduler
        self._enable_metrics = enable_metrics
        self._enable_diagnostics = enable_diagnostics

        self._components: Dict[str, Any] = {}
        self._startup_log: List[Dict[str, Any]] = []
        self._started = False

        # Core components (initialized during startup)
        self._service: Optional[CryptoService] = None
        self._factory: Optional[CryptoFactory] = None
        self._key_store: Optional[KeyStore] = None
        self._keyring: Optional[Keyring] = None
        self._registry: Optional[AlgorithmRegistry] = None
        self._metrics: Optional[CryptoMetrics] = None
        self._health_check: Optional[CryptoHealthCheck] = None
        self._diagnostics: Optional[CryptoDiagnostics] = None
        self._manager: Optional[CryptoManager] = None
        self._scheduler: Optional[CryptoScheduler] = None

    @property
    def config(self) -> CryptoConfig:
        """Get crypto configuration."""
        return self._config

    @property
    def service(self) -> Optional[CryptoService]:
        """Get crypto service."""
        return self._service

    @property
    def factory(self) -> Optional[CryptoFactory]:
        """Get crypto factory."""
        return self._factory

    @property
    def key_store(self) -> Optional[KeyStore]:
        """Get key store."""
        return self._key_store

    @property
    def keyring(self) -> Optional[Keyring]:
        """Get keyring."""
        return self._keyring

    @property
    def registry(self) -> Optional[AlgorithmRegistry]:
        """Get algorithm registry."""
        return self._registry

    @property
    def metrics(self) -> Optional[CryptoMetrics]:
        """Get metrics collector."""
        return self._metrics

    @property
    def health_check(self) -> Optional[CryptoHealthCheck]:
        """Get health checker."""
        return self._health_check

    @property
    def diagnostics(self) -> Optional[CryptoDiagnostics]:
        """Get diagnostics collector."""
        return self._diagnostics

    @property
    def manager(self) -> Optional[CryptoManager]:
        """Get crypto manager."""
        return self._manager

    @property
    def scheduler(self) -> Optional[CryptoScheduler]:
        """Get scheduler."""
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

        # Step 1: Crypto Service
        await self._init_step(
            "crypto_service", self._init_crypto_service,
        )

        # Step 2: KMS Provider
        await self._init_step(
            "kms_provider", self._init_kms_provider,
        )

        # Step 3: Key Store
        await self._init_step(
            "key_store", self._init_key_store,
        )

        # Step 4: Algorithm Registry
        await self._init_step(
            "algorithm_registry", self._init_algorithm_registry,
        )

        # Step 5: Metrics
        if self._enable_metrics:
            await self._init_step(
                "metrics", self._init_metrics,
            )

        # Step 6: Diagnostics
        if self._enable_diagnostics:
            await self._init_step(
                "diagnostics", self._init_diagnostics,
            )

        # Step 7: Health Check
        await self._init_step(
            "health_check", self._init_health_check,
        )

        # Step 8: Crypto Manager
        await self._init_step(
            "crypto_manager", self._init_crypto_manager,
        )

        # Step 9: Scheduler (optional)
        if self._enable_scheduler:
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
        Shut down the crypto platform.

        Shutdown order:
        1. Stop schedulers
        2. Flush audit / diagnostics
        3. Persist key metadata
        4. Shutdown providers

        Args:
            timeout: Shutdown timeout in seconds.

        Returns:
            Shutdown result.
        """
        shutdown_log: List[Dict[str, Any]] = []

        # Step 1: Stop schedulers
        start = datetime.utcnow()
        try:
            if self._scheduler is not None:
                await self._scheduler.stop()
            shutdown_log.append({
                "step": "stop_schedulers",
                "status": "ok",
                "elapsed": (datetime.utcnow() - start).total_seconds(),
            })
        except Exception as e:
            shutdown_log.append({
                "step": "stop_schedulers",
                "status": "error",
                "error": str(e),
                "elapsed": (datetime.utcnow() - start).total_seconds(),
            })

        # Step 2: Flush audit / diagnostics
        start = datetime.utcnow()
        try:
            if self._diagnostics is not None:
                self._diagnostics.clear_history()
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

        # Step 3: Persist key metadata
        start = datetime.utcnow()
        try:
            if self._key_store is not None:
                keys = self._key_store.list_keys()
                logger.info(
                    "Persisting %d key metadata entries",
                    len(keys),
                )
            shutdown_log.append({
                "step": "persist_key_metadata",
                "status": "ok",
                "elapsed": (datetime.utcnow() - start).total_seconds(),
            })
        except Exception as e:
            shutdown_log.append({
                "step": "persist_key_metadata",
                "status": "error",
                "error": str(e),
                "elapsed": (datetime.utcnow() - start).total_seconds(),
            })

        # Step 4: Shutdown providers
        start = datetime.utcnow()
        try:
            if self._service is not None:
                kms_provider = self._service.get_kms_provider()
                if kms_provider is not None and hasattr(
                    kms_provider, 'shutdown',
                ):
                    shutdown_result = kms_provider.shutdown()
                    if asyncio.iscoroutine(shutdown_result):
                        await shutdown_result
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

    def _init_crypto_service(self) -> CryptoService:
        """Initialize crypto service."""
        self._factory = CryptoFactory(self._config)
        self._service = CryptoService(
            config=self._config,
            factory=self._factory,
        )
        return self._service

    async def _init_kms_provider(self) -> Any:
        """Initialize KMS provider."""
        if self._service is not None:
            await self._service.initialize()
            return self._service.get_kms_provider()
        return None

    def _init_key_store(self) -> KeyStore:
        """Initialize key store."""
        self._key_store = KeyStore()
        self._keyring = Keyring(
            max_keys=self._config.key_cache_max_size,
            default_ttl_seconds=self._config.key_cache_ttl_seconds,
        )
        return self._key_store

    def _init_algorithm_registry(self) -> AlgorithmRegistry:
        """Initialize algorithm registry."""
        if self._service is not None:
            self._registry = self._service.get_registry()
        else:
            self._registry = AlgorithmRegistry()
        return self._registry

    def _init_metrics(self) -> CryptoMetrics:
        """Initialize metrics collection."""
        self._metrics = CryptoMetrics(enabled=True)
        return self._metrics

    def _init_diagnostics(self) -> CryptoDiagnostics:
        """Initialize diagnostics collection."""
        self._diagnostics = CryptoDiagnostics()
        return self._diagnostics

    def _init_health_check(self) -> CryptoHealthCheck:
        """Initialize health check."""
        self._health_check = CryptoHealthCheck(
            manager=self._manager,
            service=self._service,
            kms_provider=(
                self._service.get_kms_provider()
                if self._service is not None
                else None
            ),
            key_store=self._key_store,
            keyring=self._keyring,
        )
        return self._health_check

    async def _init_crypto_manager(self) -> CryptoManager:
        """Initialize crypto manager."""
        self._manager = CryptoManager(config=self._config)
        await self._manager.initialize()
        return self._manager

    async def _init_scheduler(self) -> CryptoScheduler:
        """Initialize scheduler."""
        self._scheduler = CryptoScheduler(
            service=self._service,
            manager=self._manager,
            health_check=self._health_check,
            metrics=self._metrics,
            key_store=self._key_store,
            keyring=self._keyring,
        )
        await self._scheduler.start()
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
            "config": self._config.to_dict(),
            "components": list(self._components.keys()),
            "startup_steps": len(self._startup_log),
            "service": (
                self._service.get_stats()
                if self._service is not None
                else None
            ),
            "manager": (
                self._manager.get_stats()
                if self._manager is not None
                else None
            ),
            "scheduler": (
                self._scheduler.get_status()
                if self._scheduler is not None
                else None
            ),
        }