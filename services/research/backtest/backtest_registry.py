"""Backtest Registry — central registry for strategies, benchmarks, cost models, and execution models.

Maintains dynamic registrations of strategy types, benchmark configurations,
cost models, and execution modules discoverable at runtime.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class StrategyCategory(str, Enum):
    """Predefined strategy categories."""

    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    TREND_FOLLOWING = "trend_following"
    ARBITRAGE = "arbitrage"
    MARKET_MAKING = "market_making"
    PAIRS_TRADING = "pairs_trading"
    STATISTICAL = "statistical"
    FUNDAMENTAL = "fundamental"
    EVENT_DRIVEN = "event_driven"
    FACTOR_BASED = "factor_based"
    ML_BASED = "ml_based"
    CUSTOM = "custom"


class BenchmarkType(str, Enum):
    EQUITY = "equity"
    BOND = "bond"
    COMMODITY = "commodity"
    CUSTOM = "custom"
    ABSOLUTE = "absolute"  # fixed rate, e.g. 3%


class BacktestRegistry:
    """Central registry for backtesting components.

    Registers:
    * Strategy types → factory callables
    * Benchmark configurations
    * Cost models → model callables
    * Execution models → executor callables
    * Slippage models → slippage callables
    * Liquidity models → liquidity callables
    """

    def __init__(self) -> None:
        self._strategy_types: Dict[str, Type] = {}
        self._strategy_factories: Dict[str, Callable] = {}
        self._benchmarks: Dict[str, Dict[str, Any]] = {}
        self._cost_models: Dict[str, Type] = {}
        self._execution_models: Dict[str, Callable] = {}
        self._slippage_models: Dict[str, Callable] = {}
        self._liquidity_models: Dict[str, Callable] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}

    # ── strategy registration ──────────────────────────────────────────────

    def register_strategy_type(
        self,
        name: str,
        strategy_cls: Type,
        factory: Optional[Callable] = None,
    ) -> None:
        """Register a strategy class and optional factory."""
        self._strategy_types[name] = strategy_cls
        if factory:
            self._strategy_factories[name] = factory
        logger.info("Registered strategy type: %s → %s", name, strategy_cls.__name__)

    def get_strategy_type(self, name: str) -> Optional[Type]:
        return self._strategy_types.get(name)

    def create_strategy(self, name: str, **kwargs) -> Any:
        factory = self._strategy_factories.get(name)
        if factory:
            return factory(**kwargs)
        cls = self._strategy_types.get(name)
        if cls:
            return cls(**kwargs)
        raise KeyError(f"Unknown strategy type: {name}")

    def list_strategy_types(self) -> List[str]:
        return sorted(self._strategy_types.keys())

    # ── benchmark registration ─────────────────────────────────────────────

    def register_benchmark(
        self,
        symbol: str,
        benchmark_type: BenchmarkType = BenchmarkType.EQUITY,
        label: Optional[str] = None,
        currency: str = "CNY",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a benchmark configuration."""
        self._benchmarks[symbol] = {
            "symbol": symbol,
            "type": benchmark_type,
            "label": label or symbol,
            "currency": currency,
            "metadata": metadata or {},
        }
        logger.info("Registered benchmark: %s (%s)", symbol, benchmark_type.value)

    def get_benchmark(self, symbol: str) -> Optional[Dict[str, Any]]:
        return self._benchmarks.get(symbol)

    def list_benchmarks(self) -> List[str]:
        return sorted(self._benchmarks.keys())

    # ── cost model registration ────────────────────────────────────────────

    def register_cost_model(self, name: str, model_cls: Type) -> None:
        """Register a transaction cost model class."""
        self._cost_models[name] = model_cls
        logger.info("Registered cost model: %s → %s", name, model_cls.__name__)

    def get_cost_model(self, name: str) -> Optional[Type]:
        return self._cost_models.get(name)

    def list_cost_models(self) -> List[str]:
        return sorted(self._cost_models.keys())

    # ── execution model registration ───────────────────────────────────────

    def register_execution_model(self, name: str, executor: Callable) -> None:
        """Register an execution model function."""
        self._execution_models[name] = executor
        logger.info("Registered execution model: %s", name)

    def get_execution_model(self, name: str) -> Optional[Callable]:
        return self._execution_models.get(name)

    def list_execution_models(self) -> List[str]:
        return sorted(self._execution_models.keys())

    # ── slippage model registration ────────────────────────────────────────

    def register_slippage_model(self, name: str, model: Callable) -> None:
        """Register a slippage model function."""
        self._slippage_models[name] = model
        logger.info("Registered slippage model: %s", name)

    def get_slippage_model(self, name: str) -> Optional[Callable]:
        return self._slippage_models.get(name)

    def list_slippage_models(self) -> List[str]:
        return sorted(self._slippage_models.keys())

    # ── liquidity model registration ───────────────────────────────────────

    def register_liquidity_model(self, name: str, model: Callable) -> None:
        """Register a liquidity model function."""
        self._liquidity_models[name] = model
        logger.info("Registered liquidity model: %s", name)

    def get_liquidity_model(self, name: str) -> Optional[Callable]:
        return self._liquidity_models.get(name)

    def list_liquidity_models(self) -> List[str]:
        return sorted(self._liquidity_models.keys())

    # ── event handler registration ─────────────────────────────────────────

    def register_event_handler(self, event_type: str, handler: Callable) -> None:
        """Register an event handler for a specific event type."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
        logger.info("Registered event handler for %s: %s", event_type, handler.__name__)

    def get_event_handlers(self, event_type: str) -> List[Callable]:
        return self._event_handlers.get(event_type, [])

    def list_event_types(self) -> List[str]:
        return sorted(self._event_handlers.keys())

    # ── summary ────────────────────────────────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        """Return a summary of all registered components."""
        return {
            "strategy_types": len(self._strategy_types),
            "benchmarks": len(self._benchmarks),
            "cost_models": len(self._cost_models),
            "execution_models": len(self._execution_models),
            "slippage_models": len(self._slippage_models),
            "liquidity_models": len(self._liquidity_models),
            "event_handlers": sum(len(v) for v in self._event_handlers.values()),
        }
