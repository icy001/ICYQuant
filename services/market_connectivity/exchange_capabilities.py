"""
Exchange Capabilities — Registry for tracking what each exchange supports
including order types, market data feeds, asset classes, and features.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class Capability(str, Enum):
    """Standard exchange capabilities."""
    SPOT_TRADING = "spot_trading"
    MARGIN_TRADING = "margin_trading"
    FUTURES_TRADING = "futures_trading"
    OPTIONS_TRADING = "options_trading"
    PERPETUAL_SWAPS = "perpetual_swaps"

    # Market Data
    ORDERBOOK_L1 = "orderbook_l1"
    ORDERBOOK_L2 = "orderbook_l2"
    ORDERBOOK_L3 = "orderbook_l3"
    TRADES = "trades"
    TICKER = "ticker"
    KLINE = "kline"
    FUNDING_RATE = "funding_rate"
    OPEN_INTEREST = "open_interest"

    # Order Types
    MARKET_ORDER = "market_order"
    LIMIT_ORDER = "limit_order"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    OCO = "oco"
    ICEBERG = "iceberg"
    TWAP = "twap"
    VWAP = "vwap"

    # Account
    BALANCE = "balance"
    POSITIONS = "positions"
    ORDER_HISTORY = "order_history"
    TRADE_HISTORY = "trade_history"

    # Advanced
    WEBSOCKET = "websocket"
    REST = "rest"
    GRPC = "grpc"
    FIX = "fix"
    MULTICAST = "multicast"
    SMART_ORDER_ROUTING = "smart_order_routing"
    PAPER_TRADING = "paper_trading"


@dataclass
class ExchangeCapabilities:
    """Capabilities profile for a specific exchange."""
    exchange_id: str
    capabilities: set[Capability] = field(default_factory=set)
    asset_classes: set[str] = field(default_factory=set)
    trading_pairs_count: int = 0
    rate_limit_requests_per_second: float = 0.0
    rate_limit_orders_per_second: float = 0.0
    supports_multi_account: bool = False
    supports_sub_accounts: bool = False
    supports_cross_margin: bool = False
    supports_isolated_margin: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def has_capability(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def has_asset_class(self, asset_class: str) -> bool:
        return asset_class in self.asset_classes


class ExchangeCapabilityRegistry:
    """
    Registry for managing exchange capability profiles.

    Tracks what each exchange supports: trading types, order types,
    market data feeds, protocols, and asset classes.

    Usage::

        registry = ExchangeCapabilityRegistry()
        await registry.initialize()
        await registry.register("binance", ExchangeCapabilities(
            exchange_id="binance",
            capabilities={Capability.SPOT_TRADING, Capability.WEBSOCKET},
        ))
        caps = await registry.get("binance")
    """

    def __init__(self) -> None:
        self._profiles: dict[str, ExchangeCapabilities] = {}

    async def initialize(self) -> None:
        """Initialize the capability registry."""
        logger.info("ExchangeCapabilityRegistry initialized.")

    async def register(self, exchange_id: str, profile: ExchangeCapabilities) -> None:
        """Register or update an exchange's capability profile."""
        self._profiles[exchange_id] = profile
        logger.info("Capabilities registered for %s: %d capabilities", exchange_id, len(profile.capabilities))

    async def unregister(self, exchange_id: str) -> bool:
        """Remove an exchange's capability profile."""
        if exchange_id in self._profiles:
            del self._profiles[exchange_id]
            return True
        return False

    async def get(self, exchange_id: str) -> Optional[ExchangeCapabilities]:
        """Get capabilities for a specific exchange."""
        return self._profiles.get(exchange_id)

    async def has_capability(self, exchange_id: str, capability: Capability) -> bool:
        """Check if an exchange supports a specific capability."""
        profile = self._profiles.get(exchange_id)
        return profile is not None and profile.has_capability(capability)

    async def find_exchanges_with_capability(
        self, capability: Capability
    ) -> list[str]:
        """Find all exchanges supporting a specific capability."""
        return [
            eid for eid, profile in self._profiles.items()
            if profile.has_capability(capability)
        ]

    async def find_exchanges_with_asset_class(
        self, asset_class: str
    ) -> list[str]:
        """Find all exchanges supporting a specific asset class."""
        return [
            eid for eid, profile in self._profiles.items()
            if profile.has_asset_class(asset_class)
        ]

    async def list_all(self) -> list[ExchangeCapabilities]:
        """List all registered capability profiles."""
        return list(self._profiles.values())

    async def get_summary(self) -> dict[str, Any]:
        """Get a summary of all capabilities."""
        all_caps: set[Capability] = set()
        all_assets: set[str] = set()
        for profile in self._profiles.values():
            all_caps.update(profile.capabilities)
            all_assets.update(profile.asset_classes)

        return {
            "total_exchanges": len(self._profiles),
            "unique_capabilities": len(all_caps),
            "unique_asset_classes": len(all_assets),
            "capabilities": sorted([c.value for c in all_caps]),
            "asset_classes": sorted(all_assets),
        }
