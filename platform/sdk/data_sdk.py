"""
ICYQuant Platform SDK - Data SDK

Interface for data provider plugins.
Supports multiple data sources: market data, research data, alternative data.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import uuid

from . import PluginBase


class DataProviderType(str, Enum):
    MARKET = "market"
    RESEARCH = "research"
    ALTERNATIVE = "alternative"
    FUNDAMENTAL = "fundamental"
    NEWS = "news"
    SENTIMENT = "sentiment"
    ECONOMIC = "economic"


@dataclass
class DataSnapshot:
    provider: str
    data_type: str
    symbols: List[str]
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict:
        return {
            "id": self.snapshot_id,
            "provider": self.provider,
            "dataType": self.data_type,
            "symbols": self.symbols,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


class DataProviderPlugin(PluginBase):
    """
    Abstract base class for data provider plugins.

    Data providers must implement:
    - fetch(symbols, fields, start, end): Fetch historical data
    - subscribe(symbols, callback): Subscribe to real-time data
    - get_latest(symbol, fields): Get latest data
    """

    def __init__(self, provider_type: DataProviderType = DataProviderType.MARKET):
        super().__init__()
        self._provider_type = provider_type
        self._subscriptions: Dict[str, Any] = {}
        self._cache: Dict[str, DataSnapshot] = {}

    @abstractmethod
    def fetch(
        self,
        symbols: List[str],
        fields: List[str],
        start: datetime,
        end: datetime,
    ) -> DataSnapshot:
        """Fetch historical data for symbols."""
        ...

    @abstractmethod
    def get_latest(
        self,
        symbol: str,
        fields: List[str],
    ) -> DataSnapshot:
        """Get latest data for a symbol."""
        ...

    def subscribe(self, symbol: str, callback: Any) -> str:
        sub_id = f"sub_{symbol}_{len(self._subscriptions)}"
        self._subscriptions[sub_id] = callback
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        if sub_id in self._subscriptions:
            del self._subscriptions[sub_id]
            return True
        return False

    def get_type(self) -> DataProviderType:
        return self._provider_type

    def initialize(self, config: Dict[str, Any]) -> bool:
        self._config = config
        self._initialized = True
        return True

    def start(self) -> bool:
        self._running = True
        return True

    def stop(self) -> bool:
        self._running = False
        return True

    def health_check(self) -> bool:
        return self._initialized

    def get_status(self) -> Dict[str, Any]:
        status = super().get_status()
        status["providerType"] = self._provider_type.value
        status["subscriptions"] = len(self._subscriptions)
        return status


class DataSDK:
    """
    SDK for managing data provider plugins.
    """

    def __init__(self):
        self._providers: Dict[str, DataProviderPlugin] = {}
        self._snapshots: List[DataSnapshot] = []

    def register(self, provider: DataProviderPlugin) -> str:
        name = provider.__class__.__name__
        self._providers[name] = provider
        return name

    def get_provider(self, name: str) -> Optional[DataProviderPlugin]:
        return self._providers.get(name)

    def list_providers(self) -> List[str]:
        return list(self._providers.keys())

    def fetch(
        self,
        provider_name: str,
        symbols: List[str],
        fields: List[str],
        start: datetime,
        end: datetime,
    ) -> Optional[DataSnapshot]:
        provider = self._providers.get(provider_name)
        if not provider:
            return None
        snapshot = provider.fetch(symbols, fields, start, end)
        self._snapshots.append(snapshot)
        return snapshot

    def get_recent_snapshots(self, limit: int = 50) -> List[DataSnapshot]:
        return self._snapshots[-limit:]
