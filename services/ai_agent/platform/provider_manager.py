"""Provider Manager — unified management of LLM provider connections.

The ProviderManager centralizes configuration and lifecycle management for all
LLM providers (OpenAI, Anthropic, Google, Azure, local models). It provides a
uniform interface regardless of the underlying provider.

Supported providers:
    - OpenAI (GPT-4, GPT-4o, GPT-3.5)
    - Anthropic (Claude 3, Claude 3.5)
    - Google (Gemini 1.5, Gemini 2.0)
    - Azure OpenAI
    - Local / self-hosted models
    - Private clusters
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProviderType(str, Enum):
    """Supported LLM provider types."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE_OPENAI = "azure_openai"
    LOCAL = "local"
    PRIVATE_CLUSTER = "private_cluster"


@dataclass
class ProviderConfig:
    """Configuration for a single provider connection."""
    provider_type: ProviderType
    api_key: str = ""
    base_url: str = ""
    default_model: str = ""
    timeout_sec: float = 120.0
    max_retries: int = 3
    rate_limit_rpm: int = 500
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderStatus:
    """Runtime status of a provider connection."""
    provider_type: ProviderType
    available: bool = True
    last_check: float = field(default_factory=time.monotonic)
    latency_ms: float = 0.0
    error_count: int = 0
    consecutive_errors: int = 0
    total_calls: int = 0


class ProviderManager:
    """Unified management of all LLM provider connections.

    Handles provider registration, health checking, and connection lifecycle.
    Provides a uniform interface for all supported providers.

    Usage:
        pm = ProviderManager()
        await pm.initialize()
        pm.register_provider("openai_main", ProviderConfig(provider_type=ProviderType.OPENAI, api_key="..."))
        status = pm.get_provider_status("openai_main")
    """

    def __init__(self) -> None:
        self._providers: Dict[str, ProviderConfig] = {}
        self._statuses: Dict[str, ProviderStatus] = {}
        self._initialized: bool = False
        logger.info("ProviderManager created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("ProviderManager initialized")

    async def shutdown(self) -> None:
        self._providers.clear()
        self._statuses.clear()
        self._initialized = False
        logger.info("ProviderManager shutdown complete")

    def register_provider(self, name: str, config: ProviderConfig) -> None:
        """Register a new provider connection."""
        self._providers[name] = config
        self._statuses[name] = ProviderStatus(provider_type=config.provider_type)
        logger.info("ProviderManager: registered %s (%s)", name, config.provider_type.value)

    def unregister_provider(self, name: str) -> bool:
        """Remove a provider connection."""
        if name in self._providers:
            del self._providers[name]
            self._statuses.pop(name, None)
            return True
        return False

    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        return self._providers.get(name)

    def get_provider_status(self, name: str) -> Optional[ProviderStatus]:
        return self._statuses.get(name)

    def list_providers(self, provider_type: Optional[ProviderType] = None) -> List[str]:
        """List registered provider names, optionally filtered by type."""
        if provider_type:
            return [n for n, c in self._providers.items() if c.provider_type == provider_type]
        return sorted(self._providers.keys())

    def record_call(self, name: str, latency_ms: float, success: bool) -> None:
        """Record a provider call result for health tracking."""
        status = self._statuses.get(name)
        if not status:
            return
        status.last_check = time.monotonic()
        status.latency_ms = latency_ms
        status.total_calls += 1
        if success:
            status.consecutive_errors = 0
        else:
            status.error_count += 1
            status.consecutive_errors += 1
            if status.consecutive_errors >= 5:
                status.available = False
                logger.warning("ProviderManager: %s marked unavailable (consecutive_errors=%d)", name, status.consecutive_errors)

    def mark_available(self, name: str) -> None:
        """Manually mark a provider as available."""
        status = self._statuses.get(name)
        if status:
            status.available = True
            status.consecutive_errors = 0

    def get_available_providers(self) -> List[str]:
        """List all currently available providers."""
        return [n for n, s in self._statuses.items() if s.available]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "total_providers": len(self._providers),
            "available_providers": len(self.get_available_providers()),
            "providers": {
                name: {
                    "type": config.provider_type.value,
                    "available": self._statuses[name].available if name in self._statuses else False,
                    "latency_ms": round(self._statuses[name].latency_ms, 2) if name in self._statuses else 0,
                    "total_calls": self._statuses[name].total_calls if name in self._statuses else 0,
                }
                for name, config in self._providers.items()
            },
        }
