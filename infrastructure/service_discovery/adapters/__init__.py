"""Registry adapter implementations and factory.

Exports the abstract ``RegistryAdapter`` and concrete adapters for
memory, etcd, consul, and kubernetes backends, along with an
``AdapterFactory`` for creating adapters by name.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .base import RegistryAdapter
from .consul import ConsulAdapter
from .etcd import EtcdAdapter
from .kubernetes import KubernetesAdapter
from .memory import MemoryAdapter

logger = logging.getLogger(__name__)

__all__ = [
    "RegistryAdapter",
    "MemoryAdapter",
    "EtcdAdapter",
    "ConsulAdapter",
    "KubernetesAdapter",
    "AdapterFactory",
]


class AdapterFactory:
    """Factory for creating registry adapters by name.

    Supported adapter names: ``memory``, ``etcd``, ``consul``,
    ``kubernetes``.
    """

    _registry: Dict[str, type] = {
        "memory": MemoryAdapter,
        "etcd": EtcdAdapter,
        "consul": ConsulAdapter,
        "kubernetes": KubernetesAdapter,
    }

    @classmethod
    def create(
        cls,
        name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> RegistryAdapter:
        """Create an adapter by name.

        Args:
            name: Adapter type name (case-insensitive).
            config: Optional configuration mapping passed as keyword
                arguments to the adapter constructor.

        Returns:
            A new ``RegistryAdapter`` instance.

        Raises:
            ValueError: If the adapter name is not recognized.
        """
        key = (name or "").lower().strip()
        adapter_cls = cls._registry.get(key)
        if adapter_cls is None:
            raise ValueError(
                f"Unknown adapter type '{name}'. "
                f"Supported: {sorted(cls._registry.keys())}"
            )
        config = dict(config) if config else {}
        logger.debug("Creating adapter '%s' with config %s.", key, config)
        return adapter_cls(**config)

    @classmethod
    def supported_adapters(cls) -> list:
        """Return the list of supported adapter names."""
        return sorted(cls._registry.keys())

    @classmethod
    def register_adapter(cls, name: str, adapter_cls: type) -> None:
        """Register a custom adapter type.

        Args:
            name: Adapter type name.
            adapter_cls: A ``RegistryAdapter`` subclass.
        """
        cls._registry[(name or "").lower().strip()] = adapter_cls
