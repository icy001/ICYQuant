"""AUM (Assets Under Management) Tracker.

Monitors fund AUM over time, tracks flows, and computes
AUM-based metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from services.fund.models import Fund


@dataclass
class AUMRecord:
    """Point-in-time AUM snapshot."""

    fund_id: str
    date: date
    aum: float
    nav: float
    net_flow: float  # subscriptions - redemptions (daily)
    pnl: float  # mark-to-market P&L (daily)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, object]:
        return {
            "fund_id": self.fund_id,
            "date": self.date.isoformat(),
            "aum": self.aum,
            "nav": self.nav,
            "net_flow": self.net_flow,
            "pnl": self.pnl,
            "timestamp": self.timestamp.isoformat(),
        }


class AUMTracker:
    """Tracks and projects AUM.

    Usage::

        tracker = AUMTracker()
        tracker.record(fund, net_flow=5_000_000, pnl=2_300_000)
        record = tracker.current(fund.fund_id)
        growth = tracker.growth_rate(fund.fund_id, days=30)
    """

    def __init__(self) -> None:
        self._history: Dict[str, List[AUMRecord]] = {}
        self._latest: Dict[str, AUMRecord] = {}

    def record(
        self,
        fund: Fund,
        net_flow: float = 0.0,
        pnl: float = 0.0,
    ) -> AUMRecord:
        """Record a new AUM data point."""
        record = AUMRecord(
            fund_id=fund.fund_id,
            date=fund.nav_date,
            aum=fund.aum,
            nav=fund.nav,
            net_flow=net_flow,
            pnl=pnl,
        )
        if fund.fund_id not in self._history:
            self._history[fund.fund_id] = []
        self._history[fund.fund_id].append(record)
        self._latest[fund.fund_id] = record
        return record

    def current(self, fund_id: str) -> Optional[AUMRecord]:
        """Get latest AUM record."""
        return self._latest.get(fund_id)

    def history(self, fund_id: str) -> List[AUMRecord]:
        """Get full AUM history for a fund."""
        return self._history.get(fund_id, [])

    def growth_rate(self, fund_id: str, days: int = 30) -> float:
        """Annualised AUM growth rate over the last N days."""
        records = self._history.get(fund_id, [])
        if len(records) < 2:
            return 0.0

        start = max(0, len(records) - days - 1)
        end = len(records) - 1

        start_aum = records[start].aum
        end_aum = records[end].aum

        if start_aum <= 0:
            return 0.0

        actual_days = (records[end].date - records[start].date).days
        if actual_days <= 0:
            return 0.0

        # CAGR
        ratio = end_aum / start_aum
        return (ratio ** (365.0 / actual_days) - 1.0) * 100.0

    def total_inflows(self, fund_id: str) -> float:
        """Sum of all positive net flows."""
        return sum(r.net_flow for r in self._history.get(fund_id, []) if r.net_flow > 0)

    def total_outflows(self, fund_id: str) -> float:
        """Sum of all negative net flows (absolute value)."""
        return abs(sum(r.net_flow for r in self._history.get(fund_id, []) if r.net_flow < 0))

    def summary(self, fund_id: str) -> Dict[str, object]:
        """AUM summary for the fund."""
        latest = self._latest.get(fund_id)
        if latest is None:
            return {"fund_id": fund_id, "aum": 0, "error": "no data"}

        return {
            "fund_id": fund_id,
            "current_aum": latest.aum,
            "current_nav": latest.nav,
            "date": latest.date.isoformat(),
            "30d_growth_rate_pct": round(self.growth_rate(fund_id, 30), 2),
            "total_inflows": self.total_inflows(fund_id),
            "total_outflows": self.total_outflows(fund_id),
            "data_points": len(self._history.get(fund_id, [])),
        }
