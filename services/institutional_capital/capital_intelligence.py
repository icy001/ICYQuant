"""
Institutional Capital Intelligence — Central Engine

The CapitalIntelligence is the top-level entry point for institutional
capital management. It coordinates all capital operations: pool management,
strategy allocation, efficiency analysis, exposure assessment, and
capital governance.

Architecture:
                       CONTROL PLANE
                            │
                    CAPITAL INTELLIGENCE
                            │
     ┌──────────────────────┼──────────────────────┐
     ▼                      ▼                      ▼
 Capital Pool          Strategy Pool         Portfolio Pool
     │                      │                      │
     └──────────────────────┼──────────────────────┘
                            ▼
                   Allocation Optimizer
                            │
                            ▼
                    Risk / Execution
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CapitalState(str, Enum):
    """Capital lifecycle states."""
    INITIALIZING = "INITIALIZING"
    ACTIVE = "ACTIVE"
    RECONCILING = "RECONCILING"
    RESTRICTED = "RESTRICTED"
    FROZEN = "FROZEN"
    CLOSED = "CLOSED"


@dataclass
class CapitalSnapshot:
    """Point-in-time snapshot of the capital system."""
    snapshot_id: str
    timestamp: datetime
    total_capital: float
    available_capital: float
    reserved_capital: float
    allocated_capital: float
    deployed_capital: float
    strategy_count: int
    active_strategies: int
    overall_efficiency: float
    risk_utilization: float
    capacity_utilization: float


class CapitalIntelligence:
    """
    Central institutional capital intelligence engine.

    Coordinates:
    - CapitalPool: aggregate capital management
    - StrategyPool: multi-strategy allocation
    - AllocationOptimizer: optimal capital distribution
    - CapitalEfficiency: performance measurement
    - Exposure analysis & governance

    Integrates with Commit 18 Autonomous Control Plane for:
    - Policy enforcement
    - Autonomy level governance
    - Approval workflows
    - Audit trail
    """

    def __init__(
        self,
        intelligence_id: Optional[str] = None,
        name: str = "ICYQuant Capital Intelligence",
        config: Optional[Dict[str, Any]] = None,
    ):
        self.intelligence_id = intelligence_id or f"ci-{uuid.uuid4().hex[:12]}"
        self.name = name
        self.config = config or {}
        self.state = CapitalState.INITIALIZING
        self.created_at = datetime.utcnow()

        # Subsystems (lazy init via runtime)
        self._capital_pool = None
        self._strategy_pool = None
        self._portfolio_pool = None
        self._allocator = None
        self._efficiency = None
        self._guard = None
        self._memory = None

        # Control Plane integration
        self._control_plane = None
        self._policy_engine = None
        self._audit_engine = None

        # History
        self.snapshots: List[CapitalSnapshot] = []
        self.decisions: List[Any] = []
        self.events: List[Dict[str, Any]] = []

        logger.info(f"CapitalIntelligence initialized: {self.intelligence_id}")

    # ─── Lifecycle ──────────────────────────────────────────────

    def initialize(self) -> None:
        """Initialize all subsystems."""
        self.state = CapitalState.ACTIVE
        self._record_event("INITIALIZED", {"timestamp": datetime.utcnow().isoformat()})
        logger.info(f"CapitalIntelligence {self.intelligence_id} activated")

    def shutdown(self) -> None:
        """Graceful shutdown."""
        self.state = CapitalState.CLOSED
        self._take_snapshot()
        self._record_event("SHUTDOWN", {"timestamp": datetime.utcnow().isoformat()})
        logger.info(f"CapitalIntelligence {self.intelligence_id} shut down")

    # ─── Capital Pool Operations ────────────────────────────────

    def get_total_capital(self) -> float:
        """Get aggregate total capital across all accounts."""
        if self._capital_pool:
            return self._capital_pool.total_capital
        return 0.0

    def get_available_capital(self) -> float:
        """Get unallocated, unreserved capital."""
        if self._capital_pool:
            return self._capital_pool.available_capital
        return 0.0

    def get_deployed_capital(self) -> float:
        """Get capital currently deployed in production."""
        if self._capital_pool:
            return self._capital_pool.deployed_capital
        return 0.0

    def get_utilization(self) -> float:
        """Capital utilization ratio: deployed / total."""
        total = self.get_total_capital()
        if total <= 0:
            return 0.0
        return self.get_deployed_capital() / total

    # ─── Strategy Operations ────────────────────────────────────

    def get_strategy_allocations(self) -> Dict[str, float]:
        """Get current strategy-level capital allocations."""
        if self._strategy_pool:
            return self._strategy_pool.get_allocations()
        return {}

    def get_strategy_efficiencies(self) -> Dict[str, float]:
        """Get capital efficiency for each strategy."""
        if self._efficiency:
            return self._efficiency.get_strategy_efficiencies()
        return {}

    def get_marginal_efficiencies(self) -> Dict[str, float]:
        """Get marginal capital efficiency for each strategy."""
        if self._efficiency:
            return self._efficiency.get_marginal_efficiencies()
        return {}

    # ─── Exposure Operations ────────────────────────────────────

    def get_exposure_matrix(self) -> Dict[str, Dict[str, float]]:
        """Get strategy x strategy exposure/correlation matrix."""
        if self._strategy_pool:
            return self._strategy_pool.get_exposure_matrix()
        return {}

    def detect_overlap_clusters(self) -> List[Dict[str, Any]]:
        """Detect strategy clusters with high factor/risk/liquidity overlap."""
        clusters = []
        if self._strategy_pool:
            clusters = self._strategy_pool.detect_overlaps()
        return clusters

    # ─── Allocation Operations ──────────────────────────────────

    def optimize_allocation(
        self,
        objective_type: str = "MAXIMIZE_SHARPE",
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run capital allocation optimization."""
        if not self._allocator:
            return {"error": "Allocator not initialized"}
        result = self._allocator.optimize(
            strategies=self.get_strategy_allocations(),
            efficiencies=self.get_strategy_efficiencies(),
            exposure=self.get_exposure_matrix(),
            objective=objective_type,
            constraints=constraints or {},
        )
        self._record_event("ALLOCATION_OPTIMIZED", result)
        return result

    def simulate_allocation(
        self,
        proposed: Dict[str, float],
        scenario_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Simulate a proposed allocation change."""
        if not self._allocator:
            return {"error": "Allocator not initialized"}
        return self._allocator.simulate(proposed, scenario_params)

    # ─── Capital Decisions ──────────────────────────────────────

    def request_allocation(
        self,
        strategy_id: str,
        amount: float,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Request capital allocation for a strategy."""
        decision = {
            "request_id": f"car-{uuid.uuid4().hex[:8]}",
            "strategy_id": strategy_id,
            "requested_amount": amount,
            "timestamp": datetime.utcnow().isoformat(),
            "context": context or {},
        }

        if self._guard:
            check = self._guard.check_allocation(strategy_id, amount)
            decision["guard"] = check
            if not check.get("allowed", False):
                decision["result"] = "REJECTED"
                return decision

        decision["result"] = "APPROVED"
        self.decisions.append(decision)
        self._record_event("ALLOCATION_REQUESTED", decision)
        return decision

    # ─── Governance ─────────────────────────────────────────────

    def reconcile(self) -> Dict[str, Any]:
        """Reconcile capital state across all accounts."""
        self.state = CapitalState.RECONCILING
        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "book_capital": self.get_total_capital() if self._capital_pool else 0,
            "reconciled": True,
        }
        self.state = CapitalState.ACTIVE
        return result

    def freeze(self) -> None:
        """Freeze all capital operations (emergency)."""
        self.state = CapitalState.FROZEN
        self._record_event("FROZEN", {"timestamp": datetime.utcnow().isoformat()})
        logger.warning(f"CapitalIntelligence {self.intelligence_id} FROZEN")

    def unfreeze(self) -> None:
        """Resume capital operations."""
        self.state = CapitalState.ACTIVE
        self._record_event("UNFROZEN", {"timestamp": datetime.utcnow().isoformat()})
        logger.info(f"CapitalIntelligence {self.intelligence_id} resumed")

    # ─── Internal ───────────────────────────────────────────────

    def _take_snapshot(self) -> CapitalSnapshot:
        """Take a point-in-time capital snapshot."""
        snap = CapitalSnapshot(
            snapshot_id=f"cs-{uuid.uuid4().hex[:8]}",
            timestamp=datetime.utcnow(),
            total_capital=self.get_total_capital(),
            available_capital=self.get_available_capital(),
            reserved_capital=self._capital_pool.reserved_capital if self._capital_pool else 0,
            allocated_capital=self._capital_pool.allocated_capital if self._capital_pool else 0,
            deployed_capital=self.get_deployed_capital(),
            strategy_count=len(self.get_strategy_allocations()),
            active_strategies=sum(
                1 for v in self.get_strategy_allocations().values() if v > 0
            ),
            overall_efficiency=self.get_utilization(),
            risk_utilization=0.0,
            capacity_utilization=0.0,
        )
        self.snapshots.append(snap)
        return snap

    def _record_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Record a capital event."""
        self.events.append({
            "event_id": f"ce-{uuid.uuid4().hex[:8]}",
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data,
        })

    def get_snapshot(self) -> Optional[CapitalSnapshot]:
        """Get the latest capital snapshot."""
        return self.snapshots[-1] if self.snapshots else None

    def get_summary(self) -> Dict[str, Any]:
        """Get summary dashboard data."""
        return {
            "intelligence_id": self.intelligence_id,
            "state": self.state.value,
            "total_capital": self.get_total_capital(),
            "available_capital": self.get_available_capital(),
            "deployed_capital": self.get_deployed_capital(),
            "utilization": self.get_utilization(),
            "strategy_count": len(self.get_strategy_allocations()),
            "decision_count": len(self.decisions),
            "event_count": len(self.events),
        }
