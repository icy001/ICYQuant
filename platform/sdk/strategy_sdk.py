"""
ICYQuant Platform SDK - Strategy SDK

Interface for trading strategy plugins.
Third-party developers can implement strategies without modifying core code.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import uuid

from . import PluginBase, PluginMetadata


class StrategyType(str, Enum):
    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    ARBITRAGE = "arbitrage"
    MARKET_MAKING = "market_making"
    EVENT_DRIVEN = "event_driven"
    ML_BASED = "ml_based"
    CUSTOM = "custom"


class SignalAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    REDUCE = "reduce"
    CLOSE = "close"


@dataclass
class StrategySignal:
    symbol: str
    action: SignalAction
    quantity: float = 0
    price: Optional[float] = None
    confidence: float = 0.0
    reason: str = ""
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.signal_id,
            "symbol": self.symbol,
            "action": self.action.value,
            "quantity": self.quantity,
            "price": self.price,
            "confidence": self.confidence,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class StrategyState:
    name: str
    strategy_type: StrategyType
    is_active: bool = False
    total_signals: int = 0
    total_trades: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    last_signal: Optional[StrategySignal] = None

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "type": self.strategy_type.value,
            "isActive": self.is_active,
            "totalSignals": self.total_signals,
            "totalTrades": self.total_trades,
            "totalPnL": self.total_pnl,
            "winRate": self.win_rate,
            "sharpeRatio": self.sharpe_ratio,
            "maxDrawdown": self.max_drawdown,
        }


class StrategyPlugin(PluginBase):
    """
    Abstract base class for strategy plugins.

    Strategy developers must implement:
    - on_bar(symbol, bar): Process a bar and return signals
    - on_tick(symbol, tick): Process a tick and return signals
    - get_state(): Return strategy state
    """

    def __init__(self, strategy_type: StrategyType = StrategyType.CUSTOM):
        super().__init__()
        self._strategy_type = strategy_type
        self._state = StrategyState(
            name=self.__class__.__name__,
            strategy_type=strategy_type,
        )
        self._parameters: Dict[str, Any] = {}

    @abstractmethod
    def on_bar(self, symbol: str, bar: Dict[str, Any]) -> Optional[StrategySignal]:
        """Process a bar and return a trading signal."""
        ...

    @abstractmethod
    def on_tick(self, symbol: str, tick: Dict[str, Any]) -> Optional[StrategySignal]:
        """Process a tick and return a trading signal."""
        ...

    @abstractmethod
    def on_order_fill(self, order: Dict[str, Any]) -> None:
        """Handle order fill notification."""
        ...

    def get_type(self) -> StrategyType:
        return self._strategy_type

    def get_state(self) -> StrategyState:
        return self._state

    def set_parameter(self, name: str, value: Any):
        self._parameters[name] = value

    def get_parameter(self, name: str, default: Any = None) -> Any:
        return self._parameters.get(name, default)

    def get_parameters(self) -> Dict[str, Any]:
        return dict(self._parameters)

    def initialize(self, config: Dict[str, Any]) -> bool:
        self._config = config
        self._parameters = config.get("parameters", {})
        self._state.is_active = config.get("active", False)
        self._initialized = True
        return True

    def start(self) -> bool:
        self._state.is_active = True
        self._running = True
        return True

    def stop(self) -> bool:
        self._state.is_active = False
        self._running = False
        return True

    def health_check(self) -> bool:
        return self._initialized

    def get_status(self) -> Dict[str, Any]:
        status = super().get_status()
        status["state"] = self._state.to_dict()
        return status


class StrategySDK:
    """
    SDK for registering and managing strategy plugins.

    Provides helper methods for strategy development.
    """

    def __init__(self):
        self._strategies: Dict[str, StrategyPlugin] = {}
        self._signals: List[StrategySignal] = []

    def register(self, strategy: StrategyPlugin) -> str:
        name = strategy.__class__.__name__
        self._strategies[name] = strategy
        return name

    def get_strategy(self, name: str) -> Optional[StrategyPlugin]:
        return self._strategies.get(name)

    def list_strategies(self) -> List[str]:
        return list(self._strategies.keys())

    def generate_signal(
        self,
        strategy_name: str,
        symbol: str,
        action: SignalAction,
        quantity: float = 0,
        confidence: float = 0.5,
        reason: str = "",
    ) -> StrategySignal:
        signal = StrategySignal(
            symbol=symbol,
            action=action,
            quantity=quantity,
            confidence=confidence,
            reason=reason,
        )
        self._signals.append(signal)
        return signal

    def get_recent_signals(self, limit: int = 50) -> List[StrategySignal]:
        return self._signals[-limit:]
