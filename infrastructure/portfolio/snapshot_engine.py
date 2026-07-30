"""Portfolio Snapshot Engine — periodic capture of portfolio state for audit and analysis."""

import time
import uuid
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SnapshotFrequency(Enum):
    INTRADAY = "intraday"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ON_DEMAND = "on_demand"
    ON_REBALANCE = "on_rebalance"


class SnapshotStatus(Enum):
    PENDING = "pending"
    CAPTURED = "captured"
    VERIFIED = "verified"
    ARCHIVED = "archived"
    ERROR = "error"


@dataclass
class SnapshotConfig:
    """Configuration for snapshot engine."""

    frequency: SnapshotFrequency = SnapshotFrequency.DAILY
    retention_days: int = 365
    compression_enabled: bool = False
    include_positions: bool = True
    include_risk_metrics: bool = True
    include_performance: bool = True
    auto_archive: bool = False
    max_snapshots_per_portfolio: int = 1000
    storage_path: str = "./snapshots"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PositionSnapshot:
    """Snapshot of a single position at a point in time."""

    symbol: str = ""
    quantity: float = 0.0
    price: float = 0.0
    market_value: float = 0.0
    weight: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    sector: str = ""
    asset_class: str = ""
    currency: str = "CNY"


@dataclass
class PortfolioSnapshot:
    """Complete portfolio snapshot at a specific timestamp."""

    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    portfolio_id: str = ""
    portfolio_name: str = ""
    timestamp: float = field(default_factory=time.time)
    frequency: SnapshotFrequency = SnapshotFrequency.DAILY
    status: SnapshotStatus = SnapshotStatus.PENDING
    nav: float = 0.0
    cash: float = 0.0
    total_assets: float = 0.0
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    leverage: float = 0.0
    daily_return: float = 0.0
    cumulative_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    volatility: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0
    positions: List[PositionSnapshot] = field(default_factory=list)
    risk_metrics: Dict[str, float] = field(default_factory=dict)
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def position_count(self) -> int:
        return len(self.positions)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "portfolio_id": self.portfolio_id,
            "portfolio_name": self.portfolio_name,
            "timestamp": self.timestamp,
            "frequency": self.frequency.value,
            "status": self.status.value,
            "nav": self.nav,
            "cash": self.cash,
            "total_assets": self.total_assets,
            "gross_exposure": self.gross_exposure,
            "net_exposure": self.net_exposure,
            "leverage": self.leverage,
            "daily_return": self.daily_return,
            "cumulative_return": self.cumulative_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "volatility": self.volatility,
            "var_95": self.var_95,
            "cvar_95": self.cvar_95,
            "position_count": self.position_count,
            "positions": [
                {
                    "symbol": p.symbol,
                    "quantity": p.quantity,
                    "price": p.price,
                    "market_value": p.market_value,
                    "weight": p.weight,
                    "unrealized_pnl": p.unrealized_pnl,
                    "sector": p.sector,
                }
                for p in self.positions
            ],
            "risk_metrics": self.risk_metrics,
            "performance_metrics": self.performance_metrics,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


class SnapshotEngine:
    """Engine for capturing and managing portfolio snapshots.

    Captures portfolio state at configurable frequencies for audit trails,
    performance analysis, and historical comparison.
    """

    def __init__(self, config: Optional[SnapshotConfig] = None):
        self.config = config or SnapshotConfig()
        self._snapshots: Dict[str, List[PortfolioSnapshot]] = {}

    def capture_snapshot(
        self,
        portfolio_id: str,
        portfolio_name: str,
        nav: float,
        cash: float,
        positions_data: List[Dict[str, Any]],
        risk_metrics: Optional[Dict[str, float]] = None,
        performance_metrics: Optional[Dict[str, float]] = None,
        frequency: Optional[SnapshotFrequency] = None,
    ) -> PortfolioSnapshot:
        """Create a new portfolio snapshot from current state data."""

        positions = []
        total_mv = 0.0
        for pd_ in positions_data:
            ps = PositionSnapshot(
                symbol=pd_.get("symbol", ""),
                quantity=pd_.get("quantity", 0.0),
                price=pd_.get("price", 0.0),
                market_value=pd_.get("market_value", 0.0),
                weight=pd_.get("weight", 0.0),
                unrealized_pnl=pd_.get("unrealized_pnl", 0.0),
                realized_pnl=pd_.get("realized_pnl", 0.0),
                sector=pd_.get("sector", ""),
                asset_class=pd_.get("asset_class", "equity"),
                currency=pd_.get("currency", "CNY"),
            )
            total_mv += ps.market_value
            positions.append(ps)

        # Recalculate weights
        if total_mv > 0:
            for ps in positions:
                ps.weight = ps.market_value / total_mv

        total_assets = total_mv + cash
        gross_exposure = sum(abs(p.market_value) for p in positions)
        leverage = gross_exposure / nav if nav > 0 else 0.0

        snapshot = PortfolioSnapshot(
            portfolio_id=portfolio_id,
            portfolio_name=portfolio_name,
            frequency=frequency or self.config.frequency,
            status=SnapshotStatus.CAPTURED,
            nav=nav,
            cash=cash,
            total_assets=total_assets,
            gross_exposure=gross_exposure,
            net_exposure=total_mv,
            leverage=leverage,
            positions=positions,
            risk_metrics=risk_metrics or {},
            performance_metrics=performance_metrics or {},
        )

        if portfolio_id not in self._snapshots:
            self._snapshots[portfolio_id] = []
        self._snapshots[portfolio_id].append(snapshot)

        # Enforce max snapshots
        if len(self._snapshots[portfolio_id]) > self.config.max_snapshots_per_portfolio:
            self._snapshots[portfolio_id] = self._snapshots[portfolio_id][
                -self.config.max_snapshots_per_portfolio:
            ]

        logger.info(
            "Snapshot %s captured for portfolio %s (NAV=%.2f, positions=%d)",
            snapshot.snapshot_id, portfolio_name, nav, len(positions),
        )
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> Optional[PortfolioSnapshot]:
        for snapshots in self._snapshots.values():
            for s in snapshots:
                if s.snapshot_id == snapshot_id:
                    return s
        return None

    def get_snapshots(
        self,
        portfolio_id: str,
        frequency: Optional[SnapshotFrequency] = None,
        limit: int = 100,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> List[PortfolioSnapshot]:
        snapshots = self._snapshots.get(portfolio_id, [])

        if frequency:
            snapshots = [s for s in snapshots if s.frequency == frequency]
        if start_time:
            snapshots = [s for s in snapshots if s.timestamp >= start_time]
        if end_time:
            snapshots = [s for s in snapshots if s.timestamp <= end_time]

        return snapshots[-limit:] if limit > 0 else snapshots

    def get_latest_snapshot(self, portfolio_id: str) -> Optional[PortfolioSnapshot]:
        snapshots = self._snapshots.get(portfolio_id, [])
        return snapshots[-1] if snapshots else None

    def compare_snapshots(
        self, snapshot_id_a: str, snapshot_id_b: str
    ) -> Dict[str, Any]:
        """Compare two snapshots and return differences."""
        snap_a = self.get_snapshot(snapshot_id_a)
        snap_b = self.get_snapshot(snapshot_id_b)

        if not snap_a or not snap_b:
            return {"error": "One or both snapshots not found"}

        positions_a = {p.symbol: p for p in snap_a.positions}
        positions_b = {p.symbol: p for p in snap_b.positions}

        added = [s for s in positions_b if s not in positions_a]
        removed = [s for s in positions_a if s not in positions_b]
        common = [s for s in positions_a if s in positions_b]

        weight_changes = {}
        for sym in common:
            w_a = positions_a[sym].weight
            w_b = positions_b[sym].weight
            weight_changes[sym] = {"from": w_a, "to": w_b, "delta": w_b - w_a}

        return {
            "nav_delta": snap_b.nav - snap_a.nav,
            "nav_change_pct": (
                ((snap_b.nav - snap_a.nav) / snap_a.nav * 100)
                if snap_a.nav else 0.0
            ),
            "exposure_delta": snap_b.net_exposure - snap_a.net_exposure,
            "new_positions": added,
            "closed_positions": removed,
            "weight_changes": weight_changes,
            "position_count_delta": snap_b.position_count - snap_a.position_count,
        }

    def clean_old_snapshots(self) -> int:
        """Remove snapshots older than retention period."""
        cutoff = time.time() - (self.config.retention_days * 86400)
        removed = 0
        for portfolio_id in list(self._snapshots.keys()):
            before = len(self._snapshots[portfolio_id])
            self._snapshots[portfolio_id] = [
                s for s in self._snapshots[portfolio_id]
                if s.timestamp >= cutoff
            ]
            removed += before - len(self._snapshots[portfolio_id])
        logger.info("Cleaned %d old snapshots", removed)
        return removed

    def get_summary(self) -> Dict[str, Any]:
        total = sum(len(v) for v in self._snapshots.values())
        return {
            "total_snapshots": total,
            "portfolios_tracked": len(self._snapshots),
            "retention_days": self.config.retention_days,
            "frequency": self.config.frequency.value,
        }
