"""In-memory registry adapter for development and testing.

Provides ``MemoryAdapter``, a thread-safe in-memory implementation of
``RegistryAdapter`` suitable for local development and unit tests.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..instance import ServiceInstance
from ..models import ServiceStatus
from ..service import Service
from .base import RegistryAdapter

logger = logging.getLogger(__name__)


class MemoryAdapter(RegistryAdapter):
    """In-memory implementation of ``RegistryAdapter``.

    Stores services in a nested dictionary keyed by namespace then
    service name. Thread-safe via a reentrant lock. ``connect`` and
    ``disconnect`` are no-ops; the adapter is always ready for use.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._services: Dict[str, Dict[str, Service]] = {}
        self._connected: bool = True
        self._register_count: int = 0
        self._deregister_count: int = 0
        self._discover_count: int = 0
        self._heartbeat_count: int = 0
        self._update_count: int = 0

    def _get_namespace(self, namespace: str) -> Dict[str, Service]:
        return self._services.setdefault(namespace or "default", {})

    def _find_service(self, service_name: str) -> Optional[Service]:
        for ns_map in self._services.values():
            service = ns_map.get(service_name)
            if service is not None:
                return service
        return None

    async def connect(self) -> None:
        self._connected = True
        logger.debug("MemoryAdapter connected (no-op).")

    async def disconnect(self) -> None:
        self._connected = False
        logger.debug("MemoryAdapter disconnected (no-op).")

    def is_connected(self) -> bool:
        return self._connected

    async def register(self, instance: ServiceInstance) -> None:
        if instance is None:
            return
        with self._lock:
            ns_map = self._get_namespace(instance.namespace)
            service = ns_map.get(instance.service_name)
            if service is None:
                service = Service(instance.service_name, instance.namespace)
                ns_map[instance.service_name] = service
            instance.status = ServiceStatus.REGISTERED
            instance.updated_at = datetime.utcnow()
            service.add_instance(instance)
            self._register_count += 1
        logger.debug(
            "Registered instance '%s/%s' in namespace '%s'.",
            instance.service_name,
            instance.instance_id,
            instance.namespace,
        )

    async def deregister(self, service_name: str, instance_id: str) -> None:
        removed = False
        with self._lock:
            for ns_map in self._services.values():
                service = ns_map.get(service_name)
                if service is None:
                    continue
                before = service.get_instance_count()
                service.remove_instance(instance_id)
                if service.get_instance_count() < before:
                    removed = True
                if service.get_instance_count() == 0:
                    ns_map.pop(service_name, None)
                break
            if removed:
                self._deregister_count += 1
        if removed:
            logger.debug(
                "Deregistered instance '%s/%s'.", service_name, instance_id
            )
        else:
            logger.debug(
                "Deregister target '%s/%s' not found.", service_name, instance_id
            )

    async def discover(
        self,
        service_name: str,
        namespace: str = "default",
        version: str = None,
    ) -> List[ServiceInstance]:
        with self._lock:
            ns_map = self._get_namespace(namespace)
            service = ns_map.get(service_name)
            instances: List[ServiceInstance] = []
            if service is not None:
                instances = list(service.get_instances(healthy_only=False))
            self._discover_count += 1
        if version:
            instances = [i for i in instances if i.version == version]
        return [i for i in instances if i.is_healthy()]

    async def get_service(
        self, service_name: str, namespace: str = "default"
    ) -> Optional[Service]:
        with self._lock:
            ns_map = self._get_namespace(namespace)
            return ns_map.get(service_name)

    async def list_services(self, namespace: str = "default") -> List[Service]:
        with self._lock:
            ns_map = self._get_namespace(namespace)
            return list(ns_map.values())

    async def heartbeat(self, service_name: str, instance_id: str) -> None:
        renewed = False
        with self._lock:
            service = self._find_service(service_name)
            if service is not None:
                instance = service.get_instance(instance_id)
                if instance is not None:
                    instance.updated_at = datetime.utcnow()
                    renewed = True
            if renewed:
                self._heartbeat_count += 1
        if not renewed:
            logger.debug(
                "Heartbeat target '%s/%s' not found.", service_name, instance_id
            )

    async def update_instance(
        self,
        service_name: str,
        instance_id: str,
        updates: Dict[str, Any],
    ) -> None:
        if not updates:
            return
        updated = False
        with self._lock:
            service = self._find_service(service_name)
            if service is not None:
                instance = service.get_instance(instance_id)
                if instance is not None:
                    for key, value in updates.items():
                        if key in ("service_name", "instance_id"):
                            continue
                        if hasattr(instance, key):
                            setattr(instance, key, value)
                    instance.updated_at = datetime.utcnow()
                    updated = True
            if updated:
                self._update_count += 1
        if not updated:
            logger.debug(
                "Update target '%s/%s' not found.", service_name, instance_id
            )

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            service_count = sum(len(ns_map) for ns_map in self._services.values())
            instance_count = sum(
                service.get_instance_count()
                for ns_map in self._services.values()
                for service in ns_map.values()
            )
            namespaces = sorted(self._services.keys())
            return {
                "adapter_type": "memory",
                "connected": self._connected,
                "namespace_count": len(self._services),
                "service_count": service_count,
                "instance_count": instance_count,
                "namespaces": namespaces,
                "register_count": self._register_count,
                "deregister_count": self._deregister_count,
                "discover_count": self._discover_count,
                "heartbeat_count": self._heartbeat_count,
                "update_count": self._update_count,
            }

    def __repr__(self) -> str:
        return "MemoryAdapter(connected=True)"
