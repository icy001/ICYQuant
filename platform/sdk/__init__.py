"""
ICYQuant Platform SDK - Plugin SDK Base

Base classes and interfaces for all platform plugins.
Plugins extend these abstract base classes to integrate with the platform.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class PluginCategory(str, Enum):
    BROKER = "broker"
    INDICATOR = "indicator"
    STRATEGY = "strategy"
    AI_MODEL = "ai_model"
    RISK_RULE = "risk_rule"
    DATA_SOURCE = "data_source"
    REPORT = "report"


@dataclass
class PluginMetadata:
    name: str
    version: str = "1.0.0"
    category: PluginCategory = PluginCategory.STRATEGY
    author: str = "ICYQuant"
    description: str = ""
    tags: List[str] = field(default_factory=list)
    min_platform_version: str = "0.4.0"
    plugin_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict:
        return {
            "id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "category": self.category.value,
            "author": self.author,
            "description": self.description,
            "tags": self.tags,
            "minPlatformVersion": self.min_platform_version,
        }


class PluginBase(ABC):
    """
    Abstract base class for all platform plugins.

    All plugins must implement:
    - initialize(config): Setup plugin with configuration
    - start(): Begin plugin operation
    - stop(): Graceful shutdown
    - health_check(): Report plugin health status
    """

    def __init__(self):
        self._metadata: Optional[PluginMetadata] = None
        self._config: Dict[str, Any] = {}
        self._initialized = False
        self._running = False
        self._error = ""

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize the plugin with configuration."""
        ...

    @abstractmethod
    def start(self) -> bool:
        """Start the plugin's main operation."""
        ...

    @abstractmethod
    def stop(self) -> bool:
        """Stop the plugin gracefully."""
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Check if the plugin is healthy."""
        ...

    def is_healthy(self) -> bool:
        """Convenience method for health_check."""
        return self.health_check()

    def get_metadata(self) -> PluginMetadata:
        if self._metadata is None:
            self._metadata = PluginMetadata(
                name=self.__class__.__name__,
                description=self.__class__.__doc__ or "",
            )
        return self._metadata

    def set_metadata(self, metadata: PluginMetadata):
        self._metadata = metadata

    def get_config(self) -> Dict[str, Any]:
        return dict(self._config)

    def is_initialized(self) -> bool:
        return self._initialized

    def is_running(self) -> bool:
        return self._running

    def get_error(self) -> str:
        return self._error

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.__class__.__name__,
            "initialized": self._initialized,
            "running": self._running,
            "error": self._error,
        }
