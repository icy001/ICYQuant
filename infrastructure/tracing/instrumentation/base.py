"""
Base instrumentation interface.

Defines the abstract contract that all
auto-instrumentations must implement,
ensuring consistent lifecycle management
and behavior across all instrumented
components.

Instrumentation Lifecycle:
1. register() -> install() -> active
2. shutdown() -> uninstall() -> inactive
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class Instrumentation(ABC):
    """
    Base class for all auto-instrumentations.

    Each instrumentation wraps a specific
    library or framework, creating spans
    for operations and propagating trace
    context automatically.

    Subclasses must implement install()
    and uninstall() to hook into the
    target library.

    Usage:
        class MyInstrumentation(Instrumentation):
            name = "my-lib"
            version = "1.0"

            async def install(self):
                # Patch the library
                ...

            async def uninstall(self):
                # Restore original functions
                ...
    """

    name: str = ""
    version: str = "1.0"

    def __init__(
        self,
        tracer: Optional[Any] = None,
    ) -> None:
        """
        Initialize instrumentation.

        Args:
            tracer: Optional Tracer instance. Uses default if None.
        """

        self._tracer = tracer
        self._installed: bool = False
        self._config: Dict[str, Any] = {}

    @property
    def is_installed(
        self,
    ) -> bool:
        """Check if instrumentation is currently active."""
        return self._installed

    @property
    def tracer(
        self,
    ) -> Any:
        """Get the tracer instance."""
        if self._tracer is None:
            from ..tracer import Tracer
            self._tracer = Tracer()
        return self._tracer

    @tracer.setter
    def tracer(
        self,
        value: Any,
    ) -> None:
        """Set the tracer instance."""
        self._tracer = value

    def configure(
        self,
        **kwargs: Any,
    ) -> "Instrumentation":
        """
        Configure instrumentation options.

        Args:
            **kwargs: Configuration options.

        Returns:
            Self for chaining.
        """

        self._config.update(kwargs)
        return self

    def get_config(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """Get a configuration value."""
        return self._config.get(key, default)

    @abstractmethod
    async def install(
        self,
    ) -> None:
        """
        Apply instrumentation patches.

        This method should monkey-patch or
        wrap the target library to intercept
        operations and create spans.
        """
        ...

    @abstractmethod
    async def uninstall(
        self,
    ) -> None:
        """
        Remove instrumentation patches.

        This method should restore the
        original functions/methods that
        were patched during install().
        """
        ...

    async def enable(
        self,
    ) -> None:
        """
        Enable instrumentation (install + mark).

        Safe to call multiple times; only
        installs once.
        """

        if not self._installed:
            await self.install()
            self._installed = True

    async def disable(
        self,
    ) -> None:
        """
        Disable instrumentation (uninstall + mark).

        Safe to call multiple times; only
        uninstalls once.
        """

        if self._installed:
            await self.uninstall()
            self._installed = False

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """Get instrumentation status."""

        return {
            "name": self.name,
            "version": self.version,
            "installed": self._installed,
            "config": dict(self._config),
        }


class InstrumentationRegistry:
    """
    Registry for all available instrumentations.

    Stores metadata about each instrumentation,
    including its supported versions and
    availability status.
    """

    def __init__(
        self,
    ) -> None:
        """Initialize registry."""

        self._registered: Dict[str, Instrumentation] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        instrumentation: Instrumentation,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register an instrumentation.

        Args:
            instrumentation: Instrumentation instance.
            metadata: Optional metadata (supports, version, etc.).
        """

        self._registered[instrumentation.name] = instrumentation
        self._metadata[instrumentation.name] = metadata or {}

    def unregister(
        self,
        name: str,
    ) -> None:
        """
        Unregister an instrumentation.

        Args:
            name: Instrumentation name.
        """

        if name in self._registered:
            del self._registered[name]
        if name in self._metadata:
            del self._metadata[name]

    def get(
        self,
        name: str,
    ) -> Optional[Instrumentation]:
        """Get an instrumentation by name."""
        return self._registered.get(name)

    def list_all(
        self,
    ) -> List[str]:
        """List all registered instrumentation names."""
        return list(self._registered.keys())

    def get_metadata(
        self,
        name: str,
    ) -> Dict[str, Any]:
        """Get metadata for an instrumentation."""
        return self._metadata.get(name, {})

    def get_all_status(
        self,
    ) -> Dict[str, Dict[str, Any]]:
        """Get status of all instrumentations."""
        return {
            name: instr.get_status()
            for name, instr in self._registered.items()
        }
