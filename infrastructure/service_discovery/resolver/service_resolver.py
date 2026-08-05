"""Service resolver with selector strategies.

Provides ``ServiceResolver`` for resolving healthy service instances
and endpoints from the registry using a pluggable selection
strategy. Adapted from the original ``resolver.py`` for the
resolver subpackage.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from ..endpoint import ServiceEndpoint
from ..exceptions import ResolverError, ServiceNotFoundError, ServiceUnavailableError
from ..instance import ServiceInstance
from ..registry import ServiceRegistry
from ..selector import RoundRobinSelector, ServiceSelector

logger = logging.getLogger(__name__)


class ServiceResolver:
    """Resolves healthy service instances from the registry.

    Args:
        registry: The ``ServiceRegistry`` to resolve against.
        selector: Optional selection strategy. Defaults to
            ``RoundRobinSelector``.
    """

    def __init__(
        self,
        registry: ServiceRegistry,
        selector: Optional[ServiceSelector] = None,
    ) -> None:
        if registry is None:
            raise ResolverError("Registry is required for the resolver.")
        self._registry = registry
        self._lock = threading.RLock()
        self._selector: ServiceSelector = selector if selector is not None else RoundRobinSelector()
        self._resolve_count = 0
        self._resolve_all_count = 0
        self._resolve_endpoint_count = 0
        self._failure_count = 0

    async def resolve(
        self,
        service_name: str,
        namespace: str = "default",
        version: str = None,
    ) -> Optional[ServiceInstance]:
        """Resolve a single healthy instance.

        Args:
            service_name: The logical service name.
            namespace: The namespace to resolve in.
            version: Optional version filter.

        Returns:
            The selected ``ServiceInstance`` or None if unavailable.

        Raises:
            ServiceUnavailableError: If no healthy instances exist.
            ResolverError: If resolution fails unexpectedly.
        """
        try:
            instances = await self._registry.discover(
                service_name, namespace=namespace, version=version
            )
            with self._lock:
                self._resolve_count += 1
            if not instances:
                logger.debug(
                    "No instances available for '%s' in '%s'.",
                    service_name,
                    namespace,
                )
                return None
            with self._lock:
                selected = self._selector.select(instances)
            if selected is None:
                raise ServiceUnavailableError(
                    f"No instance selected for '{service_name}' in '{namespace}'."
                )
            logger.debug(
                "Resolved instance '%s' for service '%s'.",
                selected.instance_id,
                service_name,
            )
            return selected
        except (ServiceNotFoundError, ServiceUnavailableError):
            with self._lock:
                self._failure_count += 1
            raise
        except Exception as e:
            with self._lock:
                self._failure_count += 1
            raise ResolverError(
                f"Failed to resolve service '{service_name}': {e}"
            ) from e

    async def resolve_all(
        self,
        service_name: str,
        namespace: str = "default",
        version: str = None,
    ) -> List[ServiceInstance]:
        """Resolve all healthy instances of a service.

        Args:
            service_name: The logical service name.
            namespace: The namespace to resolve in.
            version: Optional version filter.

        Returns:
            A list of healthy ``ServiceInstance`` objects.

        Raises:
            ResolverError: If resolution fails unexpectedly.
        """
        try:
            instances = await self._registry.discover(
                service_name, namespace=namespace, version=version
            )
            with self._lock:
                self._resolve_all_count += 1
            return instances
        except ServiceNotFoundError:
            with self._lock:
                self._failure_count += 1
            raise
        except Exception as e:
            with self._lock:
                self._failure_count += 1
            raise ResolverError(
                f"Failed to resolve all instances for '{service_name}': {e}"
            ) from e

    async def resolve_endpoint(
        self, service_name: str, namespace: str = "default"
    ) -> Optional[ServiceEndpoint]:
        """Resolve a single endpoint for a service.

        Args:
            service_name: The logical service name.
            namespace: The namespace to resolve in.

        Returns:
            A ``ServiceEndpoint`` or None if unavailable.

        Raises:
            ServiceUnavailableError: If no healthy instances exist.
            ResolverError: If resolution fails unexpectedly.
        """
        instance = await self.resolve(service_name, namespace=namespace)
        with self._lock:
            self._resolve_endpoint_count += 1
        if instance is None:
            return None
        return instance.to_endpoint()

    def set_selector(self, selector: ServiceSelector) -> None:
        """Set the selection strategy.

        Args:
            selector: The ``ServiceSelector`` to use.
        """
        if selector is None:
            raise ResolverError("Selector cannot be None.")
        with self._lock:
            self._selector = selector
        logger.debug("Service resolver selector set to %s.", type(selector).__name__)

    def get_selector(self) -> ServiceSelector:
        """Return the current selection strategy."""
        with self._lock:
            return self._selector

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the resolver.

        Returns:
            A dictionary with resolution counts and the active
            selector type.
        """
        with self._lock:
            total = (
                self._resolve_count
                + self._resolve_all_count
                + self._resolve_endpoint_count
            )
            return {
                "resolve_count": self._resolve_count,
                "resolve_all_count": self._resolve_all_count,
                "resolve_endpoint_count": self._resolve_endpoint_count,
                "failure_count": self._failure_count,
                "total_operations": total,
                "failure_rate": (self._failure_count / total) if total else 0.0,
                "selector": type(self._selector).__name__,
            }

    def __repr__(self) -> str:
        return (
            f"ServiceResolver(selector={type(self._selector).__name__}, "
            f"resolutions={self._resolve_count})"
        )