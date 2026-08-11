"""Exchange Registry — Exchange registration and management.

Manages registered exchange adapters and their configurations.
Provides exchange lookup and product/symbol routing.

Registration::

    registry = ExchangeRegistry()
    registry.register("NYSE", adapter)
    exchange = registry.get("NYSE")
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from services.execution_gateway.exchange_adapter import ExchangeAdapter

logger = logging.getLogger(__name__)


class ExchangeRegistry:
    """Exchange adapter registry.

    Stores and manages all registered exchange adapters.

    Attributes:
        _exchanges: Exchange name → ExchangeAdapter mapping
        _symbol_routing: Symbol → exchange names mapping
        _default_exchange: Default exchange name
    """

    def __init__(self) -> None:
        self._exchanges: dict[str, ExchangeAdapter] = {}
        self._symbol_routing: dict[str, list[str]] = {}
        self._default_exchange: str = ""

    # ── Registration ───────────────────────────────────────────────

    def register(self, name: str, adapter: ExchangeAdapter) -> bool:
        """Register an exchange adapter.

        Args:
            name: Exchange identifier
            adapter: Exchange adapter instance

        Returns:
            True if registered
        """
        self._exchanges[name] = adapter
        if not self._default_exchange:
            self._default_exchange = name

        logger.info("Exchange registered: %s (protocol=%s)", name, adapter.protocol.value)
        return True

    def unregister(self, name: str) -> bool:
        """Unregister an exchange.

        Args:
            name: Exchange identifier

        Returns:
            True if unregistered
        """
        if name in self._exchanges:
            del self._exchanges[name]
            if self._default_exchange == name:
                self._default_exchange = next(iter(self._exchanges), "")
            return True
        return False

    # ── Symbol Routing ─────────────────────────────────────────────

    def route_symbol(self, symbol: str, exchange_names: list[str]) -> None:
        """Configure symbol-to-exchange routing.

        Args:
            symbol: Trading symbol
            exchange_names: Ordered list of preferred exchanges
        """
        self._symbol_routing[symbol.upper()] = exchange_names
        logger.debug("Symbol %s routed to exchanges: %s", symbol, exchange_names)

    def get_exchanges_for_symbol(self, symbol: str) -> list[ExchangeAdapter]:
        """Get exchanges that can trade a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            List of ExchangeAdapter instances
        """
        names = self._symbol_routing.get(symbol.upper(), [])
        if not names:
            # Return all registered exchanges
            return list(self._exchanges.values())
        return [self._exchanges[n] for n in names if n in self._exchanges]

    # ── Query ──────────────────────────────────────────────────────

    def get(self, name: str) -> Optional[ExchangeAdapter]:
        """Get a registered exchange adapter.

        Args:
            name: Exchange identifier

        Returns:
            ExchangeAdapter or None
        """
        return self._exchanges.get(name)

    def get_default(self) -> Optional[ExchangeAdapter]:
        """Get the default exchange adapter.

        Returns:
            Default ExchangeAdapter or None
        """
        return self._exchanges.get(self._default_exchange)

    def get_all(self) -> list[ExchangeAdapter]:
        """Get all registered exchange adapters.

        Returns:
            List of all ExchangeAdapter instances
        """
        return list(self._exchanges.values())

    def get_connected(self) -> list[ExchangeAdapter]:
        """Get all connected exchange adapters.

        Returns:
            List of connected ExchangeAdapter instances
        """
        return [e for e in self._exchanges.values() if e.is_connected]

    def set_default(self, name: str) -> bool:
        """Set the default exchange.

        Args:
            name: Exchange identifier

        Returns:
            True if set successfully
        """
        if name in self._exchanges:
            self._default_exchange = name
            return True
        return False

    # ── Properties ─────────────────────────────────────────────────

    @property
    def count(self) -> int:
        return len(self._exchanges)

    @property
    def connected_count(self) -> int:
        return len(self.get_connected())

    @property
    def exchange_names(self) -> list[str]:
        return list(self._exchanges.keys())

    def to_dict(self) -> dict[str, Any]:
        """Serialize registry state."""
        return {
            "count": self.count,
            "connected_count": self.connected_count,
            "default_exchange": self._default_exchange,
            "exchanges": {n: e.to_dict() for n, e in self._exchanges.items()},
            "symbol_routing": self._symbol_routing,
        }
