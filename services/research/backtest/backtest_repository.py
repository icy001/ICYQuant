"""Backtest Repository — persistence layer for backtesting entities.

Provides CRUD operations for backtests, trades, positions, orders,
performance results, and reports with pluggable storage backends.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class BacktestRepository:
    """Pluggable persistence layer for backtesting entities.

    Supports:
    * Backtest CRUD (create, read, update, delete, list, search)
    * Trade storage with retrieval by backtest/time/asset
    * Position snapshot storage
    * Order storage
    * Performance result storage
    * Report storage

    Backend: currently in-memory; designed for swap to SQL/NoSQL.
    """

    def __init__(self, backend: str = "memory") -> None:
        self._backend = backend
        self._backtests: Dict[str, Dict[str, Any]] = {}
        self._trades: Dict[str, List[Dict[str, Any]]] = {}
        self._positions: Dict[str, List[Dict[str, Any]]] = {}
        self._orders: Dict[str, List[Dict[str, Any]]] = {}
        self._performances: Dict[str, Dict[str, Any]] = {}
        self._reports: Dict[str, Dict[str, Any]] = {}
        self._benchmarks: Dict[str, Dict[str, Any]] = {}
        self._signals: Dict[str, List[Dict[str, Any]]] = {}

    # ── backtest CRUD ──────────────────────────────────────────────────────

    async def create_backtest(self, data: Dict[str, Any]) -> Dict[str, Any]:
        bt_id = data.get("id") or str(uuid4())
        now = datetime.now(timezone.utc)
        record = {
            "id": bt_id,
            "name": data.get("name", ""),
            "strategy_id": data.get("strategy_id"),
            "status": data.get("status", "created"),
            "universe": data.get("universe", []),
            "benchmark": data.get("benchmark", "CSI300"),
            "frequency": data.get("frequency", "daily"),
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
            "initial_capital": data.get("initial_capital", 1_000_000.0),
            "config": data.get("config", {}),
            "tags": data.get("tags", []),
            "metadata": data.get("metadata", {}),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "started_at": None,
            "completed_at": None,
            "runtime_seconds": None,
        }
        self._backtests[bt_id] = record
        self._trades.setdefault(bt_id, [])
        self._positions.setdefault(bt_id, [])
        self._orders.setdefault(bt_id, [])
        self._signals.setdefault(bt_id, [])
        logger.info("Created backtest: %s (%s)", bt_id, record["name"])
        return record

    async def get_backtest(self, bt_id: str) -> Optional[Dict[str, Any]]:
        return self._backtests.get(bt_id)

    async def update_backtest(
        self, bt_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        record = self._backtests.get(bt_id)
        if not record:
            return None
        record.update(data)
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        return record

    async def delete_backtest(self, bt_id: str) -> bool:
        if bt_id in self._backtests:
            del self._backtests[bt_id]
            self._trades.pop(bt_id, None)
            self._positions.pop(bt_id, None)
            self._orders.pop(bt_id, None)
            self._signals.pop(bt_id, None)
            logger.info("Deleted backtest: %s", bt_id)
            return True
        return False

    async def list_backtests(
        self,
        status: Optional[str] = None,
        strategy_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        results = list(self._backtests.values())
        if status:
            results = [r for r in results if r.get("status") == status]
        if strategy_id:
            results = [r for r in results if r.get("strategy_id") == strategy_id]
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results[offset : offset + limit]

    # ── trade storage ──────────────────────────────────────────────────────

    async def add_trade(self, bt_id: str, trade: Dict[str, Any]) -> None:
        trade["recorded_at"] = datetime.now(timezone.utc).isoformat()
        self._trades.setdefault(bt_id, []).append(trade)

    async def add_trades(self, bt_id: str, trades: List[Dict[str, Any]]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        for t in trades:
            t["recorded_at"] = now
        self._trades.setdefault(bt_id, []).extend(trades)

    async def get_trades(
        self,
        bt_id: str,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 10000,
    ) -> List[Dict[str, Any]]:
        trades = self._trades.get(bt_id, [])
        if symbol:
            trades = [t for t in trades if t.get("symbol") == symbol]
        if start_date:
            trades = [t for t in trades if t.get("timestamp", "") >= start_date]
        if end_date:
            trades = [t for t in trades if t.get("timestamp", "") <= end_date]
        return trades[-limit:]

    async def get_trade_count(self, bt_id: str) -> int:
        return len(self._trades.get(bt_id, []))

    # ── position storage ───────────────────────────────────────────────────

    async def save_positions(
        self, bt_id: str, positions: List[Dict[str, Any]]
    ) -> None:
        self._positions[bt_id] = positions

    async def get_positions(self, bt_id: str) -> List[Dict[str, Any]]:
        return self._positions.get(bt_id, [])

    # ── order storage ──────────────────────────────────────────────────────

    async def add_order(self, bt_id: str, order: Dict[str, Any]) -> None:
        order["recorded_at"] = datetime.now(timezone.utc).isoformat()
        self._orders.setdefault(bt_id, []).append(order)

    async def get_orders(
        self, bt_id: str, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        orders = self._orders.get(bt_id, [])
        if status:
            orders = [o for o in orders if o.get("status") == status]
        return orders

    # ── performance storage ────────────────────────────────────────────────

    async def save_performance(
        self, bt_id: str, performance: Dict[str, Any]
    ) -> None:
        self._performances[bt_id] = performance

    async def get_performance(self, bt_id: str) -> Optional[Dict[str, Any]]:
        return self._performances.get(bt_id)

    # ── report storage ─────────────────────────────────────────────────────

    async def save_report(self, bt_id: str, report: Dict[str, Any]) -> None:
        self._reports[bt_id] = report

    async def get_report(self, bt_id: str) -> Optional[Dict[str, Any]]:
        return self._reports.get(bt_id)

    # ── benchmark data ─────────────────────────────────────────────────────

    async def save_benchmark_data(
        self, symbol: str, data: Dict[str, Any]
    ) -> None:
        self._benchmarks[symbol] = data

    async def get_benchmark_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        return self._benchmarks.get(symbol)

    # ── signal storage ─────────────────────────────────────────────────────

    async def add_signal(self, bt_id: str, signal: Dict[str, Any]) -> None:
        signal["recorded_at"] = datetime.now(timezone.utc).isoformat()
        self._signals.setdefault(bt_id, []).append(signal)

    async def get_signals(
        self, bt_id: str, symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        signals = self._signals.get(bt_id, [])
        if symbol:
            signals = [s for s in signals if s.get("symbol") == symbol]
        return signals

    # ── lifecycle ──────────────────────────────────────────────────────────

    async def clear(self) -> None:
        """Clear all stored data."""
        self._backtests.clear()
        self._trades.clear()
        self._positions.clear()
        self._orders.clear()
        self._performances.clear()
        self._reports.clear()
        self._benchmarks.clear()
        self._signals.clear()
        logger.info("Cleared all backtest repository data")

    async def get_stats(self) -> Dict[str, Any]:
        """Return repository statistics."""
        return {
            "backtests": len(self._backtests),
            "total_trades": sum(len(v) for v in self._trades.values()),
            "total_orders": sum(len(v) for v in self._orders.values()),
            "total_signals": sum(len(v) for v in self._signals.values()),
            "performances": len(self._performances),
            "reports": len(self._reports),
            "benchmarks": len(self._benchmarks),
            "backend": self._backend,
        }
