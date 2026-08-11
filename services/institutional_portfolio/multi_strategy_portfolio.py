"""
Multi-Strategy Portfolio — Central Portfolio Coordination Hub

The MultiStrategyPortfolio is the single entry point that coordinates
all strategies into a unified portfolio. It orchestrates:

    Strategy Pool → Signal Aggregation → Signal Netting
    → Position Netting → Portfolio Construction → Risk Aggregation
    → Capital Coordination → Rebalance → Execution

This is the "institutional portfolio manager" — not just a collection
of individual strategy P&Ls, but a coordinated, risk-aware capital allocator.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class PortfolioState(str, Enum):
    INITIALIZING = "INITIALIZING"
    ACTIVE = "ACTIVE"
    REBALANCING = "REBALANCING"
    STRESSED = "STRESSED"
    DEGRADED = "DEGRADED"
    FROZEN = "FROZEN"


@dataclass
class PortfolioSnapshot:
    snapshot_id: str
    timestamp: datetime
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    long_exposure: float = 0.0
    short_exposure: float = 0.0
    strategy_count: int = 0
    active_strategies: int = 0
    positions: int = 0
    var_95: float = 0.0
    expected_return: float = 0.0
    leverage: float = 0.0
    turnover: float = 0.0
    resilience_score: float = 1.0


class MultiStrategyPortfolio:
    """
    Central multi-strategy portfolio coordination hub.

    Coordinates:
    - Strategy Registry & Grouping
    - Signal Aggregation → Netting → Confidence
    - Position Netting → Target Positions
    - Portfolio Construction & Optimization
    - Risk Aggregation & Factor Exposure
    - Capital Coordination & Priority
    - Rebalance Engine & Turnover Control
    """

    def __init__(
        self,
        portfolio_id: Optional[str] = None,
        name: str = "ICYQuant Institutional Portfolio",
        config: Optional[Dict[str, Any]] = None,
    ):
        self.portfolio_id = portfolio_id or f"msp-{uuid.uuid4().hex[:12]}"
        self.name = name
        self.config = config or {}
        self.state = PortfolioState.INITIALIZING
        self.created_at = datetime.utcnow()

        # Subsystems (lazy init via runtime)
        self._strategy_registry = None
        self._signal_aggregator = None
        self._signal_netting = None
        self._position_netting = None
        self._portfolio_builder = None
        self._portfolio_optimizer = None
        self._risk_aggregator = None
        self._capital_coordinator = None
        self._rebalance_engine = None
        self._guard = None

        # Control plane
        self._control_plane = None

        # History
        self.snapshots: List[PortfolioSnapshot] = []
        self.events: List[Dict[str, Any]] = []

        logger.info(f"MultiStrategyPortfolio initialized: {self.portfolio_id}")

    # ─── Lifecycle ──────────────────────────────────────────

    def initialize(self) -> None:
        self.state = PortfolioState.ACTIVE
        self._record_event("INITIALIZED")

    def freeze(self) -> None:
        self.state = PortfolioState.FROZEN
        self._record_event("FROZEN")
        logger.warning(f"Portfolio {self.portfolio_id} FROZEN")

    def unfreeze(self) -> None:
        self.state = PortfolioState.ACTIVE
        self._record_event("UNFROZEN")

    # ─── Orchestration Pipeline ─────────────────────────────

    def orchestrate(self) -> Dict[str, Any]:
        """
        Full orchestration pipeline:
        1. Collect strategy signals
        2. Aggregate & net signals
        3. Net positions
        4. Compute target positions
        5. Build portfolio
        6. Aggregate risk
        7. Coordinate capital
        8. Check rebalance triggers
        9. Return orchestration plan
        """
        self.state = PortfolioState.REBALANCING
        try:
            result = {
                "portfolio_id": self.portfolio_id,
                "timestamp": datetime.utcnow().isoformat(),
                "signals": self._aggregate_signals(),
                "positions": self._net_positions(),
                "targets": self._compute_targets(),
                "risk": self._aggregate_risk(),
                "capital": self._coordinate_capital(),
                "rebalance_required": self._check_rebalance(),
            }
            self._record_event("ORCHESTRATED", result)
            self.state = PortfolioState.ACTIVE
            return result
        except Exception as e:
            logger.error(f"Orchestration failed: {e}")
            self.state = PortfolioState.DEGRADED
            return {"error": str(e)}

    # ─── Exposures ──────────────────────────────────────────

    def get_gross_exposure(self) -> float:
        return sum(self._get_positions().values()) if self._position_netting else 0.0

    def get_net_exposure(self) -> float:
        pos = self._get_positions()
        return sum(pos.values()) if pos else 0.0

    def get_leverage(self) -> float:
        net = self.get_net_exposure()
        total = 1.0  # total capital; wire from capital_coordinator
        return net / total if total > 0 else 0.0

    # ─── Strategy Quarantine ────────────────────────────────

    def quarantine_strategy(self, strategy_id: str) -> Dict[str, Any]:
        """Isolate a failing strategy without stopping the portfolio."""
        self._record_event("STRATEGY_QUARANTINED", {"strategy_id": strategy_id})
        return {
            "action": "QUARANTINED",
            "strategy_id": strategy_id,
            "portfolio_recalculated": self.orchestrate(),
        }

    def replace_strategy(self, old_id: str, new_id: str) -> Dict[str, Any]:
        """Replace a quarantined strategy."""
        self._record_event("STRATEGY_REPLACED", {"old": old_id, "new": new_id})
        return self.orchestrate()

    # ─── Summary ────────────────────────────────────────────

    def take_snapshot(self) -> PortfolioSnapshot:
        snap = PortfolioSnapshot(
            snapshot_id=f"ps-{uuid.uuid4().hex[:8]}",
            timestamp=datetime.utcnow(),
            gross_exposure=self.get_gross_exposure(),
            net_exposure=self.get_net_exposure(),
            leverage=self.get_leverage(),
            strategy_count=len(self._strategy_registry.get_all()) if self._strategy_registry else 0,
            active_strategies=len(self._strategy_registry.get_active()) if self._strategy_registry else 0,
            resilience_score=self._compute_resilience(),
        )
        self.snapshots.append(snap)
        return snap

    def get_summary(self) -> Dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "state": self.state.value,
            "net_exposure": self.get_net_exposure(),
            "gross_exposure": self.get_gross_exposure(),
            "leverage": self.get_leverage(),
            "strategies": self._strategy_registry.get_summary() if self._strategy_registry else {},
        }

    # ─── Internal ───────────────────────────────────────────

    def _aggregate_signals(self) -> Dict[str, Any]:
        if self._signal_aggregator:
            return self._signal_aggregator.aggregate()
        return {}

    def _net_positions(self) -> Dict[str, Any]:
        if self._position_netting:
            return self._position_netting.net()
        return {}

    def _compute_targets(self) -> Dict[str, Any]:
        if self._position_netting:
            return self._position_netting.get_targets()
        return {}

    def _aggregate_risk(self) -> Dict[str, Any]:
        if self._risk_aggregator:
            return self._risk_aggregator.aggregate()
        return {}

    def _coordinate_capital(self) -> Dict[str, Any]:
        if self._capital_coordinator:
            return self._capital_coordinator.coordinate()
        return {}

    def _check_rebalance(self) -> bool:
        if self._rebalance_engine:
            return self._rebalance_engine.should_rebalance()
        return False

    def _get_positions(self) -> Dict[str, float]:
        if self._position_netting:
            return self._position_netting.get_net_positions()
        return {}

    def _compute_resilience(self) -> float:
        return 1.0

    def _record_event(self, event_type: str, data: Optional[Dict] = None) -> None:
        self.events.append({
            "event_id": f"ev-{uuid.uuid4().hex[:8]}",
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data or {},
        })
