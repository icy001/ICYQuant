"""
Base Configuration Source.

Defines the abstract interface for all configuration sources.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from ..priority import ConfigurationPriority


class ConfigurationSource(ABC):
    """
    Abstract base class for configuration sources.

    All configuration sources must inherit from this
    class and implement the load() method.

    Attributes:
        name: Source name identifier.
        priority: Source priority for resolution order.
    """

    name: str = "base"
    priority: int = ConfigurationPriority.DEFAULT

    @abstractmethod
    def load(self) -> Dict[str, Any]:
        """
        Load configuration from this source.

        Returns:
            Dictionary of configuration values.
        """

        ...

    async def async_load(self) -> Dict[str, Any]:
        """
        Async load configuration.
        Default implementation just calls sync load.
        """
        return self.load()

    def is_available(self) -> bool:
        """Check if this source is currently available."""
        return True

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} priority={self.priority}>"
