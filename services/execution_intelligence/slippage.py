from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TradeRecord:
    trade_id: str
    symbol: str
    side: str
    quantity: int
    expected_price: float
    executed_price: float
    timestamp: str = ""
    venue: str = ""


@dataclass
class SlippageReport:
    trade_id: str
    symbol: str
    expected_price: float
    executed_price: float
    slippage_absolute: float
    slippage_bps: float
    direction: str  # POSITIVE / NEGATIVE / ZERO
    severity: str  # LOW / MEDIUM / HIGH / CRITICAL
    cost_impact: float = 0.0


class SlippageControlEngine:
    """Slippage Control Engine - monitors and controls execution slippage."""

    def __init__(self):
        self.slippage_threshold_bps = 10.0
        self.critical_threshold_bps = 50.0
        self.trade_log: List[SlippageReport] = []

    def measure(self, trade):
        """Measure slippage for a trade.

        Args:
            trade: Trade to analyze - can be TradeRecord dataclass or dict/symbol.

        Returns:
            Dict containing slippage measurement.
        """
        if isinstance(trade, TradeRecord):
            return self._measure_slippage(trade)
        return {"slippage": trade}

    def _measure_slippage(self, trade: TradeRecord) -> dict:
        if trade.expected_price == 0:
            slippage_abs = 0.0
            slippage_bps = 0.0
        else:
            slippage_abs = trade.executed_price - trade.expected_price
            slippage_bps = (slippage_abs / trade.expected_price) * 10000

        direction = "POSITIVE" if slippage_bps > 0 else ("NEGATIVE" if slippage_bps < 0 else "ZERO")
        severity = self._classify_slippage(abs(slippage_bps))

        cost_impact = abs(slippage_abs) * trade.quantity

        report = SlippageReport(
            trade_id=trade.trade_id,
            symbol=trade.symbol,
            expected_price=trade.expected_price,
            executed_price=trade.executed_price,
            slippage_absolute=round(slippage_abs, 4),
            slippage_bps=round(slippage_bps, 2),
            direction=direction,
            severity=severity,
            cost_impact=round(cost_impact, 2),
        )
        self.trade_log.append(report)

        return {
            "slippage": {
                "trade_id": report.trade_id,
                "symbol": report.symbol,
                "expected_price": report.expected_price,
                "executed_price": report.executed_price,
                "slippage_bps": report.slippage_bps,
                "direction": report.direction,
                "severity": report.severity,
                "cost_impact": report.cost_impact,
            }
        }

    def _classify_slippage(self, abs_bps: float) -> str:
        if abs_bps < self.slippage_threshold_bps:
            return "LOW"
        elif abs_bps < self.slippage_threshold_bps * 2:
            return "MEDIUM"
        elif abs_bps < self.critical_threshold_bps:
            return "HIGH"
        return "CRITICAL"

    def should_intervene(self, slippage_bps: float) -> bool:
        """Determine if intervention is needed based on slippage."""
        return abs(slippage_bps) > self.critical_threshold_bps

    def get_cumulative_slippage(self) -> float:
        """Get cumulative slippage across all logged trades."""
        if not self.trade_log:
            return 0.0
        return sum(r.slippage_bps for r in self.trade_log)

    def get_average_slippage(self) -> float:
        """Get average slippage across all logged trades."""
        if not self.trade_log:
            return 0.0
        return self.get_cumulative_slippage() / len(self.trade_log)
