"""Service discovery manager.

Provides ``ServiceDiscoveryManager`` as the top-level coordinator for
the service discovery module, managing the registry, resolver,
namespace manager, repository, and lifecycle with async startup and
graceful shutdown.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Dict, Optional

from .exceptions import (
    AdapterConnectionError,
    AdapterNotReadyError,
    ServiceDiscoveryError,
)
from .namespace import NamespaceManager
from .registry import InMemoryRegistryAdapter, RegistryAdapter, ServiceRegistry
from .repository import ServiceRepository
from .resolver import ServiceResolver

logger = logging.getLogger(__name__)


class ServiceDiscoveryManager:
    """Top-level coordinator for service discovery.

    Manages the registry, resolver, namespace manager, repository,
    and synchronization lifecycle. Thread-safe for status checks and
    stats; async for startup, shutdown, and synchronization.

    Args:
        adapter: Optional registry backend adapter. Defaults to an
            in-memory adapter.
        sync_interval: Synchronization interval in seconds.
    """

    def __init__(
        self,
        adapter: Optional[RegistryAdapter] = None,
        sync_interval: float = 30.0,
    ) -> None:
        self._lock = threading.RLock()
        self._namespace_manager = NamespaceManager()
        self._adapter: RegistryAdapter = (
            adapter if adapter is not None else InMemoryRegistryAdapter()
        )
        self._registry = ServiceRegistry(
            adapter=self._adapter,
            namespace_manager=self._namespace_manager,
        )
        self._resolver = ServiceResolver(self._registry)
        self._repository = ServiceRepository(ttl=sync_interval)
        self._sync_interval = float(sync_interval) if sync_interval > 0 else 30.0
        self._running = False
        self._last_sync_time: float = 0.0
        self._last_sync_result: Dict[str, int] = {"synced": 0, "errors": 0}
        self._sync_count = 0
        self._sync_task: Optional[asyncio.Task] = None

    def get_registry(self) -> ServiceRegistry:
        """Return the service registry."""
        return self._registry

    def get_resolver(self) -> ServiceResolver:
        """Return the service resolver."""
        return self._resolver

    def get_namespace_manager(self) -> NamespaceManager:
        """Return the namespace manager."""
        return self._namespace_manager

    def get_repository(self) -> ServiceRepository:
        """Return the service repository."""
        return self._repository

    def is_running(self) -> bool:
        """Return whether the manager is currently running."""
        with self._lock:
            return self._running

    async def startup(self) -> None:
        """Initialize the registry, adapter, and resolver.

        Raises:
            AdapterNotReadyError: If the adapter is not ready.
            ServiceDiscoveryError: If startup fails.
        """
        with self._lock:
            if self._running:
                logger.info("Service discovery manager is already running.")
                return
        try:
            ready = await self._adapter.is_ready()
            if not ready:
                raise AdapterNotReadyError(
                    "Registry adapter is not ready for startup."
                )
            self._repository.invalidate_all()
            with self._lock:
                self._running = True
            logger.info("Service discovery manager started successfully.")
        except AdapterNotReadyError:
            raise
        except ServiceDiscoveryError:
            raise
        except Exception as e:
            raise AdapterConnectionError(
                f"Failed to start service discovery manager: {e}"
            ) from e

    async def shutdown(self) -> None:
        """Gracefully shut down the service discovery manager.

        Cancels background synchronization, cleans up leases, and
        invalidates the repository cache.
        """
        with self._lock:
            if not self._running:
                logger.info("Service discovery manager is not running.")
                return
            self._running = False
            if self._sync_task is not None and not self._sync_task.done():
                self._sync_task.cancel()
                self._sync_task = None
        try:
            self._repository.invalidate_all()
            self._registry.lease_manager.cleanup_expired()
            logger.info("Service discovery manager shut down successfully.")
        except Exception as e:
            logger.error("Error during service discovery shutdown: %s", e)

    async def synchronize(self) -> Dict[str, int]:
        """Synchronize the local repository with the backend registry.

        Refreshes cached services from the adapter across all
        namespaces.

        Returns:
            A dictionary with ``synced`` and ``errors`` counts.
        """
        if not self.is_running():
            logger.warning("Synchronize called while manager is not running.")
            return {"synced": 0, "errors": 0}

        synced = 0
        errors = 0
        namespaces = [ns.name for ns in self._namespace_manager.list_namespaces()]
        for namespace in namespaces:
            try:
                services = await self._registry.list_services(namespace)
                for service in services:
                    self._repository.set_service(service)
                    synced += 1
            except Exception as e:
                errors += 1
                logger.warning(
                    "Synchronization failed for namespace '%s': %s",
                    namespace,
                    e,
                )
        cleaned = self._repository.cleanup_expired()
        with self._lock:
            self._sync_count += 1
            self._last_sync_time = time.time()
            self._last_sync_result = {"synced": synced, "errors": errors}
        logger.info(
            "Synchronized %d service(s) across %d namespace(s) "
            "(errors=%d, expired_cleaned=%d).",
            synced,
            len(namespaces),
            errors,
            cleaned,
        )
        return {"synced": synced, "errors": errors}

    async def _sync_loop(self) -> None:
        """Background synchronization loop."""
        logger.info(
            "Starting service discovery sync loop (interval=%ss).",
            self._sync_interval,
        )
        while self.is_running():
            try:
                await asyncio.sleep(self._sync_interval)
                if not self.is_running():
                    break
                await self.synchronize()
            except asyncio.CancelledError:
                logger.info("Service discovery sync loop cancelled.")
                break
            except Exception as e:
                logger.error("Error in service discovery sync loop: %s", e)

    def start_sync_loop(self) -> Optional[asyncio.Task]:
        """Start the background synchronization loop.

        Returns:
            The ``asyncio.Task`` for the sync loop, or None if the
            manager is not running or a loop is already active.
        """
        with self._lock:
            if not self._running:
                logger.warning(
                    "Cannot start sync loop; manager is not running."
                )
                return None
            if self._sync_task is not None and not self._sync_task.done():
                return self._sync_task
            try:
                self._sync_task = asyncio.create_task(self._sync_loop())
            except RuntimeError:
                logger.warning(
                    "No running event loop; sync loop not started."
                )
                return None
            return self._sync_task

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the manager.

        Returns:
            A dictionary with manager status, sync info, and
            component statistics.
        """
        with self._lock:
            return {
                "running": self._running,
                "sync_interval": self._sync_interval,
                "sync_count": self._sync_count,
                "last_sync_time": self._last_sync_time,
                "last_sync_result": dict(self._last_sync_result),
                "adapter_type": type(self._adapter).__name__,
                "registry_stats": self._registry.get_stats(),
                "resolver_stats": self._resolver.get_stats(),
                "repository_stats": self._repository.get_stats(),
                "namespace_stats": self._namespace_manager.get_stats(),
            }

    def __repr__(self) -> str:
        return (
            f"ServiceDiscoveryManager(running={self.is_running()}, "
            f"sync_count={self._sync_count})"
        )
