"""Global Circuit Breaker – supports multi-level trading stops."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class BreakerScope(Enum):
    GLOBAL = "global"
    STRATEGY = "strategy"
    SYMBOL = "symbol"
    BROKER = "broker"
    EXCHANGE = "exchange"


@dataclass
class BreakerEvent:
    scope: BreakerScope
    target: str
    reason: str = ""
    triggered_by: str = "manual"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class GlobalCircuitBreaker:
    """Multi-level circuit breaker for trading system.

    Supports stopping at Global, Strategy, Symbol, Broker, and Exchange levels.
    """

    def __init__(self) -> None:
        self.active = False
        self._scoped_breakers: Dict[str, BreakerEvent] = {}
        self._event_log: List[BreakerEvent] = []

    def trigger(
        self,
        scope: BreakerScope = BreakerScope.GLOBAL,
        target: str = "all",
        reason: str = "",
        triggered_by: str = "manual",
    ) -> BreakerEvent:
        """Trigger a circuit breaker at the given scope.

        Global breaker also sets self.active = True.
        """
        event = BreakerEvent(
            scope=scope,
            target=target,
            reason=reason,
            triggered_by=triggered_by,
        )
        key = f"{scope.value}:{target}"

        if scope == BreakerScope.GLOBAL:
            self.active = True
            self._scoped_breakers.clear()  # global overrides all

        self._scoped_breakers[key] = event
        self._event_log.append(event)
        return event

    def reset(
        self,
        scope: BreakerScope = BreakerScope.GLOBAL,
        target: str = "all",
    ) -> None:
        """Reset circuit breaker at the given scope."""
        key = f"{scope.value}:{target}"

        if scope == BreakerScope.GLOBAL:
            self.active = False
            self._scoped_breakers.clear()
        else:
            self._scoped_breakers.pop(key, None)

    def is_active(self, scope: BreakerScope = BreakerScope.GLOBAL, target: str = "all") -> bool:
        """Check if a specific scope/target is under circuit breaker."""
        if self.active:
            return True  # global overrides everything
        key = f"{scope.value}:{target}"
        return key in self._scoped_breakers

    def is_strategy_blocked(self, strategy_name: str) -> bool:
        """Check if a specific strategy is blocked."""
        return self.is_active(BreakerScope.STRATEGY, strategy_name)

    def is_symbol_blocked(self, symbol: str) -> bool:
        """Check if a specific symbol is blocked."""
        return self.is_active(BreakerScope.SYMBOL, symbol)

    def get_active_breakers(self) -> List[BreakerEvent]:
        """Return all currently active breaker events."""
        return list(self._scoped_breakers.values())

    def get_event_log(self, n: int = 20) -> List[BreakerEvent]:
        """Return recent breaker events."""
        return self._event_log[-n:]

    def kill_switch(self, reason: str = "Emergency kill switch") -> BreakerEvent:
        """Emergency stop — triggers global circuit breaker immediately."""
        return self.trigger(
            scope=BreakerScope.GLOBAL,
            target="all",
            reason=reason,
            triggered_by="kill_switch",
        )
