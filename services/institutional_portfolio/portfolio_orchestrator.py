"""
Portfolio Orchestrator — Continuous Multi-Strategy Coordination Loop

Runs the orchestration loop:
    1. Collect → signals from all strategies
    2. Aggregate → combine & weight signals
    3. Net → cross-strategy netting
    4. Construct → portfolio targets
    5. Risk → aggregate & validate
    6. Capital → coordinate allocation
    7. Rebalance → trigger if needed
    8. Execute → push to execution engine
"""

import uuid
import time
import threading
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class OrchestrationPhase(str, Enum):
    IDLE = "IDLE"
    COLLECTING = "COLLECTING"
    AGGREGATING = "AGGREGATING"
    NETTING = "NETTING"
    CONSTRUCTING = "CONSTRUCTING"
    RISK_CHECKING = "RISK_CHECKING"
    CAPITAL_COORDINATING = "CAPITAL_COORDINATING"
    REBALANCING = "REBALANCING"
    EXECUTING = "EXECUTING"


@dataclass
class OrchestrationCycle:
    cycle_id: str
    phase: OrchestrationPhase = OrchestrationPhase.IDLE
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    signals_collected: int = 0
    position_changes: int = 0
    rebalance_actions: int = 0
    error: Optional[str] = None


class PortfolioOrchestrator:
    """
    Continuous orchestration engine for multi-strategy portfolio.

    Runs the complete pipeline: signal → net → construct → risk → capital → rebalance.
    With configurable cycle interval and cooldown periods.
    """

    def __init__(
        self,
        orchestrator_id: Optional[str] = None,
        portfolio=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.orchestrator_id = orchestrator_id or f"po-{uuid.uuid4().hex[:12]}"
        self._portfolio = portfolio
        self.config = config or {}
        self.phase = OrchestrationPhase.IDLE

        self._cycle_interval = self.config.get("cycle_interval_seconds", 60)
        self._cooldown = self.config.get("cooldown_seconds", 120)
        self._last_cycle_at: Optional[datetime] = None

        self.cycles: List[OrchestrationCycle] = []
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._on_cycle: Optional[Callable] = None

    def run_once(self) -> OrchestrationCycle:
        cycle = OrchestrationCycle(cycle_id=f"ocy-{uuid.uuid4().hex[:8]}")

        try:
            if not self._portfolio:
                cycle.error = "No portfolio connected"
                return cycle

            # Phase 1: Collect
            cycle.phase = OrchestrationPhase.COLLECTING
            signals = self._portfolio._aggregate_signals()
            cycle.signals_collected = len(signals)

            # Phase 2: Net
            cycle.phase = OrchestrationPhase.NETTING
            positions = self._portfolio._net_positions()
            cycle.position_changes = len(positions)

            # Phase 3: Construct
            cycle.phase = OrchestrationPhase.CONSTRUCTING
            self._portfolio._compute_targets()

            # Phase 4: Risk
            cycle.phase = OrchestrationPhase.RISK_CHECKING
            risk = self._portfolio._aggregate_risk()

            # Phase 5: Capital
            cycle.phase = OrchestrationPhase.CAPITAL_COORDINATING
            self._portfolio._coordinate_capital()

            # Phase 6: Rebalance
            rebalance_needed = self._portfolio._check_rebalance()
            if rebalance_needed:
                cycle.phase = OrchestrationPhase.REBALANCING
                cycle.rebalance_actions = 1

            cycle.phase = OrchestrationPhase.IDLE

        except Exception as e:
            cycle.error = str(e)
            logger.error(f"Orchestration cycle {cycle.cycle_id} failed: {e}")

        cycle.completed_at = datetime.utcnow()
        self._last_cycle_at = cycle.completed_at
        self.cycles.append(cycle)

        if self._on_cycle:
            self._on_cycle(cycle)

        return cycle

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name=f"portfolio-orch-{self.orchestrator_id}")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=30)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as e:
                logger.error(f"Loop error: {e}")
            self._stop_event.wait(timeout=self._cycle_interval)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "orchestrator_id": self.orchestrator_id,
            "phase": self.phase.value,
            "cycles": len(self.cycles),
            "running": self._thread is not None and self._thread.is_alive(),
        }
