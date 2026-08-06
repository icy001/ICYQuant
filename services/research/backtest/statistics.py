"""Trade Statistics — comprehensive trade and position-level statistics.

Computes granular statistics from trade records for detailed
backtest analysis and report generation.

Stats::

    Trade Count → Win Rate → Profit Factor → Expectancy → Duration → Turnover
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TradeStatistics:
    """Detailed trade-level statistics."""

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    even_trades: int = 0

    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_win: float = 0.0
    max_loss: float = 0.0
    expectancy: float = 0.0

    total_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0

    avg_holding_days: float = 0.0
    max_holding_days: float = 0.0
    min_holding_days: float = float("inf")

    consecutive_wins: int = 0
    consecutive_losses: int = 0

    buy_trades: int = 0
    sell_trades: int = 0

    avg_trade_value: float = 0.0
    total_trade_value: float = 0.0

    turnover_rate: float = 0.0  # annualized

    month_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    symbol_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "even_trades": self.even_trades,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "max_win": self.max_win,
            "max_loss": self.max_loss,
            "expectancy": self.expectancy,
            "total_pnl": self.total_pnl,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "avg_holding_days": self.avg_holding_days,
            "max_holding_days": self.max_holding_days,
            "consecutive_wins": self.consecutive_wins,
            "consecutive_losses": self.consecutive_losses,
            "buy_trades": self.buy_trades,
            "sell_trades": self.sell_trades,
            "avg_trade_value": self.avg_trade_value,
            "total_trade_value": self.total_trade_value,
            "turnover_rate": self.turnover_rate,
        }


def compute_trade_statistics(
    trades: List[Dict[str, Any]],
    initial_capital: float = 1_000_000.0,
    total_days: int = 252,
) -> TradeStatistics:
    """Compute comprehensive trade statistics from trade records.

    Args:
        trades: List of trade records with side, price, quantity, pnl.
        initial_capital: Starting capital for turnover calculation.
        total_days: Total trading days for annualization.

    Returns:
        Comprehensive TradeStatistics.
    """
    stats = TradeStatistics()

    if not trades:
        return stats

    stats.total_trades = len(trades)
    stats.buy_trades = sum(1 for t in trades if t.get("side") == "buy")
    stats.sell_trades = sum(1 for t in trades if t.get("side") == "sell")

    # Compute PnL per trade (pairing)
    pairs = _pair_trades(trades)
    pnls: List[float] = []
    durations: List[float] = []
    max_consecutive_wins = 0
    max_consecutive_losses = 0
    current_wins = 0
    current_losses = 0

    for pair in pairs:
        buy = pair["buy"]
        sell = pair["sell"]
        buy_price = buy.get("price", 0)
        sell_price = sell.get("price", 0)
        qty = buy.get("quantity", 0)
        pnl = (sell_price - buy_price) * qty
        pnls.append(pnl)

        # Duration
        buy_ts = buy.get("timestamp", "")
        sell_ts = sell.get("timestamp", "")
        duration = _estimate_days(buy_ts, sell_ts)
        durations.append(duration)

        # Consecutive tracking
        if pnl > 0:
            current_wins += 1
            current_losses = 0
            max_consecutive_wins = max(max_consecutive_wins, current_wins)
        elif pnl < 0:
            current_losses += 1
            current_wins = 0
            max_consecutive_losses = max(max_consecutive_losses, current_losses)

    # Win/loss classification
    for pnl in pnls:
        if pnl > 0:
            stats.winning_trades += 1
            stats.gross_profit += pnl
            stats.max_win = max(stats.max_win, pnl)
        elif pnl < 0:
            stats.losing_trades += 1
            stats.gross_loss += abs(pnl)
            stats.max_loss = min(stats.max_loss, pnl)
        else:
            stats.even_trades += 1

    stats.total_pnl = stats.gross_profit - stats.gross_loss
    total = stats.winning_trades + stats.losing_trades + stats.even_trades
    stats.win_rate = stats.winning_trades / total if total > 0 else 0
    stats.profit_factor = stats.gross_profit / stats.gross_loss if stats.gross_loss > 0 else float("inf")
    stats.avg_win = stats.gross_profit / stats.winning_trades if stats.winning_trades > 0 else 0
    stats.avg_loss = stats.gross_loss / stats.losing_trades if stats.losing_trades > 0 else 0
    stats.expectancy = sum(pnls) / len(pnls) if pnls else 0

    # Duration stats
    if durations:
        stats.avg_holding_days = sum(durations) / len(durations)
        stats.max_holding_days = max(durations)
        stats.min_holding_days = min(durations)

    stats.consecutive_wins = max_consecutive_wins
    stats.consecutive_losses = max_consecutive_losses

    # Value stats
    stats.total_trade_value = _compute_total_value(trades)
    stats.avg_trade_value = stats.total_trade_value / total if total > 0 else 0

    # Turnover (buy-side only, annualized)
    buy_value = sum(
        t.get("quantity", 0) * t.get("price", 0)
        for t in trades if t.get("side") == "buy"
    )
    if initial_capital > 0 and total_days > 0:
        stats.turnover_rate = (buy_value / initial_capital) * (252 / total_days)

    # Per-symbol stats
    stats.symbol_stats = _compute_symbol_stats(trades)

    return stats


def _pair_trades(trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pair buy and sell trades by symbol."""
    pairs = []
    symbol_queue: Dict[str, List[Dict[str, Any]]] = {}

    for trade in sorted(trades, key=lambda t: t.get("timestamp", "")):
        symbol = trade.get("symbol", "")
        side = trade.get("side", "")
        if symbol not in symbol_queue:
            symbol_queue[symbol] = []
        if side == "buy":
            symbol_queue[symbol].append(trade)
        elif side == "sell" and symbol_queue[symbol]:
            buy = symbol_queue[symbol].pop(0)
            pairs.append({"buy": buy, "sell": trade})

    return pairs


def _estimate_days(start_ts: str, end_ts: str) -> float:
    """Estimate days between two timestamps."""
    try:
        from datetime import datetime
        start = datetime.fromisoformat(start_ts.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_ts.replace("Z", "+00:00"))
        return (end - start).total_seconds() / 86400.0
    except (ValueError, KeyError):
        return 1.0


def _compute_total_value(trades: List[Dict[str, Any]]) -> float:
    """Compute total notional value of all trades."""
    return sum(
        abs(t.get("quantity", 0)) * t.get("price", 0)
        for t in trades
    )


def _compute_symbol_stats(
    trades: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Compute per-symbol trade statistics."""
    symbol_trades: Dict[str, List[Dict[str, Any]]] = {}
    for trade in trades:
        symbol = trade.get("symbol", "UNKNOWN")
        if symbol not in symbol_trades:
            symbol_trades[symbol] = []
        symbol_trades[symbol].append(trade)

    result = {}
    for symbol, st in symbol_trades.items():
        pairs = _pair_trades(st)
        pnls = [
            (p["sell"]["price"] - p["buy"]["price"]) * p["buy"]["quantity"]
            for p in pairs
        ]
        result[symbol] = {
            "trades": len(st),
            "total_pnl": sum(pnls),
            "avg_pnl": sum(pnls) / len(pnls) if pnls else 0,
            "win_rate": sum(1 for p in pnls if p > 0) / len(pnls) if pnls else 0,
        }

    return result
