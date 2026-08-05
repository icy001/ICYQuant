"""Service registry with pluggable backend adapter.

Provides ``RegistryAdapter`` (abstract), ``InMemoryRegistryAdapter``,
and ``ServiceRegistry`` for registering, deregistering, discovering,
and updating service instances. The registry is thread-safe and
integrates with the ``NamespaceManager``.
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from .exceptions import (
    AdapterError,
    NamespaceError,
    ServiceDeregistrationError,
    ServiceDiscoveryError,
    ServiceNotFoundError,
    ServiceRegistrationError,
)
from .instance import ServiceInstance
from .lease import LeaseManager
from .lifecycle import ServiceLifecycle
from .models import ServiceStatus
from .namespace import NamespaceManager
from .service import Service
from .validator import ServiceValidator

logger = logging.getLogger(__name__)


class RegistryAdapter(ABC):
    """Abstract base class for a service registry backend adapter."""

    @abstractmethod
    async def register(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Register a service instance."""

    @abstractmethod
    async def deregister(
        self, service_name: str, instance_id: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Deregister a service instance."""

    @abstractmethod
    async def get_instances(
        self, service_name: str, namespace: str = "default"
    ) -> List[ServiceInstance]:
        """Return all instances for a service."""

    @abstractmethod
    async def list_services(self, namespace: str = "default") -> List[Service]:
        """List all services in a namespace."""

    @abstractmethod
    async def get_service(
        self, service_name: str, namespace: str = "default"
    ) -> Optional[Service]:
        """Return a service aggregate."""

    @abstractmethod
    async def update_instance(
        self,
        service_name: str,
        instance_id: str,
        updates: Dict[str, Any],
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """Update fields of a service instance."""

    @abstractmethod
    async def is_ready(self) -> bool:
        """Return whether the adapter is ready for operations."""


class InMemoryRegistryAdapter(RegistryAdapter):
    """In-memory implementation of ``RegistryAdapter``.

    Stores services in a nested dictionary keyed by namespace then
    service name. Thread-safe.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._services: Dict[str, Dict[str, Service]] = {}

    def _get_namespace(self, namespace: str) -> Dict[str, Service]:
        return self._services.setdefault(namespace or "default", {})

    async def is_ready(self) -> bool:
        return True

    async def register(self, instance: ServiceInstance) -> Dict[str, Any]:
        if instance is None:
            raise ServiceRegistrationError("Cannot register a None instance.")
        with self._lock:
            ns_map = self._get_namespace(instance.namespace)
            service = ns_map.get(instance.service_name)
            if service is None:
                service = Service(instance.service_name, instance.namespace)
                ns_map[instance.service_name] = service
            service.add_instance(instance)
            count = service.get_instance_count()
        return {
            "registered": True,
            "service_name": instance.service_name,
            "instance_id": instance.instance_id,
            "namespace": instance.namespace,
            "instance_count": count,
        }

    async def deregister(
        self, service_name: str, instance_id: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        with self._lock:
            ns_map = self._get_namespace(namespace)
            service = ns_map.get(service_name)
            if service is None:
                return {
                    "deregistered": False,
                    "service_name": service_name,
                    "instance_id": instance_id,
                    "namespace": namespace,
                    "reason": "service_not_found",
                }
            service.remove_instance(instance_id)
            remaining = service.get_instance_count()
            if remaining == 0:
                ns_map.pop(service_name, None)
        return {
            "deregistered": True,
            "service_name": service_name,
            "instance_id": instance_id,
            "namespace": namespace,
            "remaining_instances": remaining,
        }

    async def get_instances(
        self, service_name: str, namespace: str = "default"
    ) -> List[ServiceInstance]:
        with self._lock:
            ns_map = self._get_namespace(namespace)
            service = ns_map.get(service_name)
            if service is None:
                return []
            return service.get_instances(healthy_only=False)

    async def list_services(self, namespace: str = "default") -> List[Service]:
        with self._lock:
            ns_map = self._get_namespace(namespace)
            return list(ns_map.values())

    async def get_service(
        self, service_name: str, namespace: str = "default"
    ) -> Optional[Service]:
        with self._lock:
            ns_map = self._get_namespace(namespace)
            return ns_map.get(service_name)

    async def update_instance(
        self,
        service_name: str,
        instance_id: str,
        updates: Dict[str, Any],
        namespace: str = "default",
    ) -> Dict[str, Any]:
        if not updates:
            return {
                "updated": False,
                "service_name": service_name,
                "instance_id": instance_id,
                "reason": "no_updates",
            }
        with self._lock:
            ns_map = self._get_namespace(namespace)
            service = ns_map.get(service_name)
            if service is None:
                return {
                    "updated": False,
                    "service_name": service_name,
                    "instance_id": instance_id,
                    "reason": "service_not_found",
                }
            instance = service.get_instance(instance_id)
            if instance is None:
                return {
                    "updated": False,
                    "service_name": service_name,
                    "instance_id": instance_id,
                    "reason": "instance_not_found",
                }
            applied: List[str] = []
            for key, value in updates.items():
                if key in ("service_name", "instance_id"):
                    continue
                if hasattr(instance, key):
                    setattr(instance, key, value)
                    applied.append(key)
            instance.updated_at = datetime.utcnow()
        return {
            "updated": True,
            "service_name": service_name,
            "instance_id": instance_id,
            "namespace": namespace,
            "applied_fields": applied,
        }


class ServiceRegistry:
    """Service registry coordinating registration and discovery.

    Delegates storage to a ``RegistryAdapter`` and integrates with
    the ``NamespaceManager``, ``ServiceValidator``, lifecycle, and
    lease managers. All public operations are async.

    Args:
        adapter: Backend storage adapter. Defaults to an in-memory
            adapter when None.
        namespace_manager: Optional namespace manager. A default one
            is created when None.
    """

    def __init__(
        self,
        adapter: Optional[RegistryAdapter] = None,
        namespace_manager: Optional[NamespaceManager] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._adapter: RegistryAdapter = adapter if adapter is not None else InMemoryRegistryAdapter()
        self._namespace_manager = namespace_manager if namespace_manager is not None else NamespaceManager()
        self._validator = ServiceValidator()
        self._lifecycle = ServiceLifecycle()
        self._lease_manager = LeaseManager()
        self._register_count = 0
        self._deregister_count = 0
        self._discover_count = 0
        self._update_count = 0
        self._error_count = 0
        self._instance_namespaces: Dict[str, str] = {}

    @staticmethod
    def _instance_key(service_name: str, instance_id: str) -> str:
        return f"{service_name}:{instance_id}"

    def _resolve_namespace(self, service_name: str, instance_id: str) -> str:
        """Resolve the namespace for a registered instance.

        Falls back to ``default`` when the instance was not tracked
        (e.g. registered externally or before this registry existed).
        """
        with self._lock:
            return self._instance_namespaces.get(
                self._instance_key(service_name, instance_id), "default"
            )

    @property
    def adapter(self) -> RegistryAdapter:
        """Return the underlying registry adapter."""
        return self._adapter

    @property
    def namespace_manager(self) -> NamespaceManager:
        """Return the namespace manager."""
        return self._namespace_manager

    @property
    def validator(self) -> ServiceValidator:
        """Return the service validator."""
        return self._validator

    @property
    def lifecycle(self) -> ServiceLifecycle:
        """Return the lifecycle manager."""
        return self._lifecycle

    @property
    def lease_manager(self) -> LeaseManager:
        """Return the lease manager."""
        return self._lease_manager

    async def register(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Register a service instance.

        Args:
            instance: The ``ServiceInstance`` to register.

        Returns:
            A dictionary describing the registration result.

        Raises:
            ServiceRegistrationError: If validation or registration
                fails.
        """
        if instance is None:
            raise ServiceRegistrationError("Cannot register a None instance.")
        errors = self._validator.validate_instance(instance)
        if errors:
            with self._lock:
                self._error_count += 1
            raise ServiceRegistrationError(
                f"Invalid service instance: {'; '.join(errors)}"
            )
        try:
            if not await self._adapter.is_ready():
                raise AdapterError("Registry adapter is not ready.")
            instance.status = ServiceStatus.REGISTERED
            instance.updated_at = datetime.utcnow()
            result = await self._adapter.register(instance)
            self._namespace_manager.add_service_to_namespace(
                instance.namespace, instance.service_name
            )
            self._lifecycle.transition(
                instance.service_name,
                instance.instance_id,
                ServiceStatus.REGISTERED,
            )
            self._lease_manager.create_lease(
                instance.service_name, instance.instance_id
            )
            with self._lock:
                self._register_count += 1
                self._instance_namespaces[
                    self._instance_key(instance.service_name, instance.instance_id)
                ] = instance.namespace
            logger.info(
                "Registered instance '%s/%s' in namespace '%s'.",
                instance.service_name,
                instance.instance_id,
                instance.namespace,
            )
            return result
        except (ServiceDiscoveryError, NamespaceError):
            with self._lock:
                self._error_count += 1
            raise
        except Exception as e:
            with self._lock:
                self._error_count += 1
            raise ServiceRegistrationError(
                f"Failed to register instance '{instance.service_name}/{instance.instance_id}': {e}"
            ) from e

    async def deregister(
        self, service_name: str, instance_id: str
    ) -> Dict[str, Any]:
        """Deregister a service instance.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.

        Returns:
            A dictionary describing the deregistration result.

        Raises:
            ServiceDeregistrationError: If deregistration fails.
        """
        try:
            if not await self._adapter.is_ready():
                raise AdapterError("Registry adapter is not ready.")
            namespace = self._resolve_namespace(service_name, instance_id)
            result = await self._adapter.deregister(
                service_name, instance_id, namespace=namespace
            )
            if not result.get("deregistered"):
                with self._lock:
                    self._error_count += 1
                raise ServiceNotFoundError(
                    f"Service '{service_name}' or instance '{instance_id}' not found."
                )
            self._lifecycle.transition(
                service_name, instance_id, ServiceStatus.DEREGISTERED
            )
            self._lease_manager.expire_lease(service_name, instance_id)
            with self._lock:
                self._deregister_count += 1
                self._instance_namespaces.pop(
                    self._instance_key(service_name, instance_id), None
                )
            logger.info(
                "Deregistered instance '%s/%s'.", service_name, instance_id
            )
            return result
        except (ServiceDiscoveryError,):
            with self._lock:
                self._error_count += 1
            raise
        except Exception as e:
            with self._lock:
                self._error_count += 1
            raise ServiceDeregistrationError(
                f"Failed to deregister instance '{service_name}/{instance_id}': {e}"
            ) from e

    async def discover(
        self,
        service_name: str,
        namespace: str = "default",
        version: str = None,
    ) -> List[ServiceInstance]:
        """Discover service instances.

        Args:
            service_name: The logical service name.
            namespace: The namespace to discover in.
            version: Optional version filter.

        Returns:
            A list of matching ``ServiceInstance`` objects.

        Raises:
            ServiceNotFoundError: If no instances are found.
        """
        try:
            with self._lock:
                self._discover_count += 1
            instances = await self._adapter.get_instances(service_name, namespace)
            if version:
                instances = [i for i in instances if i.version == version]
            healthy = [i for i in instances if i.is_healthy()]
            if not healthy:
                logger.debug(
                    "No healthy instances found for '%s' in '%s'.",
                    service_name,
                    namespace,
                )
            return healthy
        except ServiceDiscoveryError:
            with self._lock:
                self._error_count += 1
            raise
        except Exception as e:
            with self._lock:
                self._error_count += 1
            raise ServiceNotFoundError(
                f"Failed to discover service '{service_name}': {e}"
            ) from e

    async def get_service(
        self, service_name: str, namespace: str = "default"
    ) -> Optional[Service]:
        """Return a service aggregate by name.

        Args:
            service_name: The logical service name.
            namespace: The namespace to look up.

        Returns:
            The ``Service`` or None if not found.
        """
        return await self._adapter.get_service(service_name, namespace)

    async def list_services(self, namespace: str = "default") -> List[Service]:
        """List all services in a namespace.

        Args:
            namespace: The namespace to list.

        Returns:
            A list of ``Service`` objects.
        """
        return await self._adapter.list_services(namespace)

    async def update_instance(
        self,
        service_name: str,
        instance_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update fields of a registered service instance.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.
            updates: Mapping of fields to update.

        Returns:
            A dictionary describing the update result.

        Raises:
            ServiceNotFoundError: If the instance cannot be found.
        """
        try:
            if not await self._adapter.is_ready():
                raise AdapterError("Registry adapter is not ready.")
            if "status" in updates and isinstance(updates["status"], ServiceStatus):
                self._lifecycle.transition(
                    service_name, instance_id, updates["status"]
                )
            namespace = self._resolve_namespace(service_name, instance_id)
            result = await self._adapter.update_instance(
                service_name, instance_id, updates, namespace=namespace
            )
            if not result.get("updated"):
                with self._lock:
                    self._error_count += 1
                raise ServiceNotFoundError(
                    f"Cannot update; instance '{instance_id}' of service "
                    f"'{service_name}' not found."
                )
            with self._lock:
                self._update_count += 1
            logger.info(
                "Updated instance '%s/%s': %s",
                service_name,
                instance_id,
                result.get("applied_fields", []),
            )
            return result
        except ServiceDiscoveryError:
            with self._lock:
                self._error_count += 1
            raise
        except Exception as e:
            with self._lock:
                self._error_count += 1
            raise ServiceDiscoveryError(
                f"Failed to update instance '{service_name}/{instance_id}': {e}"
            ) from e

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the registry.

        Returns:
            A dictionary with operation counts and adapter readiness.
        """
        with self._lock:
            return {
                "register_count": self._register_count,
                "deregister_count": self._deregister_count,
                "discover_count": self._discover_count,
                "update_count": self._update_count,
                "error_count": self._error_count,
                "adapter_type": type(self._adapter).__name__,
                "validator_stats": self._validator.get_stats(),
                "lifecycle_stats": self._lifecycle.get_stats(),
                "lease_stats": self._lease_manager.get_stats(),
                "namespace_stats": self._namespace_manager.get_stats(),
            }

    def __repr__(self) -> str:
        return (
            f"ServiceRegistry(adapter={type(self._adapter).__name__}, "
            f"registrations={self._register_count})"
        )
