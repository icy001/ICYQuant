"""
Instrumentation manager.

Provides async lifecycle management
for all auto-instrumentations, handling
registration, installation, and shutdown
in a coordinated manner.

Usage:
    manager = InstrumentationManager()

    # Register
    await manager.register(FastAPIInstrumentation())
    await manager.register(RedisInstrumentation())

    # Shutdown all
    await manager.shutdown()
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import Instrumentation, InstrumentationRegistry


class InstrumentationManager:
    """
    Async-safe instrumentation manager.

    Manages the full lifecycle of all
    auto-instrumentations, providing
    async registration, installation,
    and coordinated shutdown.

    Features:
    - Async register/unregister
    - Bulk install/uninstall
    - Graceful shutdown
    - Status reporting
    - Dependency ordering (future)

    Usage:
        manager = InstrumentationManager()
        await manager.register(FastAPIInstrumentation())
        await manager.register(SQLAlchemyInstrumentation())
        # All are now instrumented

        await manager.shutdown()
        # All are now uninstrumented
    """

    def __init__(
        self,
        registry: Optional[InstrumentationRegistry] = None,
    ) -> None:
        """
        Initialize manager.

        Args:
            registry: Optional InstrumentationRegistry instance.
        """

        self._registry = registry or InstrumentationRegistry()
        self._items: Dict[str, Instrumentation] = {}
        self._installed_order: List[str] = []

    @property
    def registry(
        self,
    ) -> InstrumentationRegistry:
        """Get the instrumentation registry."""
        return self._registry

    @property
    def installed_count(
        self,
    ) -> int:
        """Get number of installed instrumentations."""
        return len(self._installed_order)

    @property
    def registered_count(
        self,
    ) -> int:
        """Get number of registered instrumentations."""
        return len(self._items)

    async def register(
        self,
        item: Instrumentation,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register and install an instrumentation.

        Args:
            item: Instrumentation to register.
            metadata: Optional metadata.
        """

        self._registry.register(item, metadata=metadata)
        self._items[item.name] = item
        await item.enable()
        if item.name not in self._installed_order:
            self._installed_order.append(item.name)

    async def unregister(
        self,
        name: str,
    ) -> None:
        """
        Unregister and uninstall an instrumentation.

        Args:
            name: Instrumentation name.
        """

        item = self._items.get(name)
        if item is not None:
            await item.disable()
        self._registry.unregister(name)
        self._items.pop(name, None)
        if name in self._installed_order:
            self._installed_order.remove(name)

    async def enable(
        self,
        name: str,
    ) -> bool:
        """
        Enable a specific instrumentation.

        Args:
            name: Instrumentation name.

        Returns:
            True if enabled successfully.
        """

        item = self._items.get(name)
        if item is None:
            return False
        await item.enable()
        if name not in self._installed_order:
            self._installed_order.append(name)
        return True

    async def disable(
        self,
        name: str,
    ) -> bool:
        """
        Disable a specific instrumentation.

        Args:
            name: Instrumentation name.

        Returns:
            True if disabled successfully.
        """

        item = self._items.get(name)
        if item is None:
            return False
        await item.disable()
        if name in self._installed_order:
            self._installed_order.remove(name)
        return True

    async def install_all(
        self,
    ) -> List[str]:
        """
        Install all registered instrumentations.

        Returns:
            List of successfully installed names.
        """

        installed = []
        for name, item in self._items.items():
            try:
                await item.enable()
                installed.append(name)
                if name not in self._installed_order:
                    self._installed_order.append(name)
            except Exception:
                pass
        return installed

    async def uninstall_all(
        self,
    ) -> None:
        """Uninstall all instrumentations (reverse order)."""

        for name in reversed(self._installed_order):
            item = self._items.get(name)
            if item is not None:
                try:
                    await item.disable()
                except Exception:
                    pass
        self._installed_order.clear()

    async def shutdown(
        self,
    ) -> None:
        """
        Graceful shutdown of all instrumentations.

        Uninstalls in reverse installation order
        to handle dependencies correctly.
        """

        await self.uninstall_all()

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """Get manager status."""

        return {
            "registered": list(self._items.keys()),
            "installed": list(self._installed_order),
            "registered_count": self.registered_count,
            "installed_count": self.installed_count,
            "items": {
                name: item.get_status()
                for name, item in self._items.items()
            },
        }
