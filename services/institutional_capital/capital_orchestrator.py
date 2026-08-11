"""
Capital Orchestrator — Multi-Strategy Coordination

The CapitalOrchestrator coordinates capital flows across multiple strategies.
It implements the orchestration loop:

    1. Monitor → efficiency, utilization, exposures
    2. Detect → opportunities & risks
    3. Optimize → allocation proposal
    4. Validate → constraints & guardrails
    5. Execute → through controller → manager
    6. Observe → feedback & learning

This is the "autonomous capital allocator" that runs continuously.
"""

import uuid
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class OrchestratorState(str, Enum):
    """Orchestrator run states."""
    IDLE = "IDLE"
    MONITORING = "MONITORING"
    OPTIMIZING = "OPTIMIZING"
    EXECUTING = "EXECUTING"
    COOLDOWN = "COOLDOWN"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"


class OrchestrationTrigger(str, Enum):
    """What triggered this orchestration cycle."""
    SCHEDULED = "SCHEDULED"
    EFFICIENCY_THRESHOLD = "EFFICIENCY_THRESHOLD"
    UTILIZATION_THRESHOLD = "UTILIZATION_THRESHOLD"
    CONCENTRATION_ALERT = "CONCENTRATION_ALERT"
    CORRELATION_BREACH = "CORRELATION_BREACH"
    MANUAL = "MANUAL"
    STRATEGY_EVENT = "STRATEGY_EVENT"
    POOL_CHANGE = "POOL_CHANGE"


@dataclass
class OrchestrationSignal:
    """A signal detected during monitoring that may trigger action."""
    signal_type: str
    severity: str  # INFO, WARNING, CRITICAL
    source: str
    metric: str
    value: float
    threshold: float
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OrchestrationCycle:
    """Record of one orchestration cycle."""
    cycle_id: str
    trigger: OrchestrationTrigger
    started_at: datetime
    completed_at: Optional[datetime] = None
    signals_detected: List[OrchestrationSignal] = field(default_factory=list)
    proposal: Optional[Dict[str, Any]] = None
    actions_taken: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "INITIATED"


class CapitalOrchestrator:
    """
    Autonomous multi-strategy capital orchestrator.

    Runs the continuous orchestration loop:
    Monitor rich metrics → Detect reallocation signals → Optimize
    → Validate against guardrails → Execute via controller.

    Key behaviors:
    - Event-driven: reacts to efficiency drops, utilization changes
    - Conservative: only acts when signals are clear (configurable thresholds)
    - Cooldown: prevents oscillation with configurable cooldown periods
    - Audit: logs every cycle for retrospective analysis
    """

    def __init__(
        self,
        orchestrator_id: Optional[str] = None,
        intelligence=None,
        controller=None,
        manager=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.orchestrator_id = orchestrator_id or f"co-{uuid.uuid4().hex[:12]}"
        self._intelligence = intelligence
        self._controller = controller
        self._manager = manager
        self.config = config or {}

        self.state = OrchestratorState.IDLE

        # Orchestration cycle
        self._cycle_interval_seconds = self.config.get("cycle_interval_seconds", 300)
        self._cooldown_seconds = self.config.get("cooldown_seconds", 900)
        self._last_action_at: Optional[datetime] = None

        # Thresholds
        self._min_efficiency_threshold = self.config.get("min_efficiency_threshold", 0.05)
        self._max_concentration = self.config.get("max_concentration", 0.30)
        self._max_correlation = self.config.get("max_correlation", 0.70)
        self._min_utilization = self.config.get("min_utilization", 0.50)
        self._max_utilization = self.config.get("max_utilization", 0.95)

        # Reallocation constraints
        self._max_reallocation_pct = self.config.get("max_reallocation_pct", 0.20)
        self._min_reallocation_amount = self.config.get("min_reallocation_amount", 10000)

        # Cycle history
        self.cycles: List[OrchestrationCycle] = []
        self.current_cycle: Optional[OrchestrationCycle] = None

        # Threading
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Callbacks
        self._on_cycle_complete: Optional[Callable] = None
        self._on_signal: Optional[Callable] = None

        logger.info(f"CapitalOrchestrator initialized: {self.orchestrator_id}")

    # ─── Orchestration Loop ─────────────────────────────────────

    def run_once(self, trigger: OrchestrationTrigger = OrchestrationTrigger.SCHEDULED) -> OrchestrationCycle:
        """Run one complete orchestration cycle."""
        if self.state == OrchestratorState.STOPPED:
            logger.warning("Orchestrator is stopped")
            return self._empty_cycle(trigger, "STOPPED")

        # Check cooldown
        if not self._can_act():
            logger.debug("Orchestrator in cooldown")
            return self._empty_cycle(trigger, "COOLDOWN")

        cycle = OrchestrationCycle(
            cycle_id=f"ocyc-{uuid.uuid4().hex[:8]}",
            trigger=trigger,
            started_at=datetime.utcnow(),
        )
        self.current_cycle = cycle

        try:
            # Step 1: Monitor
            self.state = OrchestratorState.MONITORING
            signals = self._monitor()
            cycle.signals_detected = signals

            if self._on_signal:
                for s in signals:
                    self._on_signal(s)

            # Step 2: Decide if action needed
            if not self._should_act(signals):
                cycle.status = "NO_ACTION_NEEDED"
                cycle.completed_at = datetime.utcnow()
                self.cycles.append(cycle)
                self.state = OrchestratorState.IDLE
                return cycle

            # Step 3: Optimize
            self.state = OrchestratorState.OPTIMIZING
            proposal = self._optimize(signals)
            cycle.proposal = proposal

            if not proposal or proposal.get("status") == "NO_CHANGE":
                cycle.status = "NO_CHANGE_PROPOSED"
                cycle.completed_at = datetime.utcnow()
                self.cycles.append(cycle)
                self.state = OrchestratorState.IDLE
                return cycle

            # Step 4: Validate
            if not self._validate_proposal(proposal):
                cycle.status = "PROPOSAL_REJECTED"
                cycle.completed_at = datetime.utcnow()
                self.cycles.append(cycle)
                self.state = OrchestratorState.IDLE
                return cycle

            # Step 5: Execute
            self.state = OrchestratorState.EXECUTING
            actions = self._execute_proposal(proposal)
            cycle.actions_taken = actions

            cycle.status = "EXECUTED"
            cycle.completed_at = datetime.utcnow()
            self._last_action_at = datetime.utcnow()
            self.cycles.append(cycle)

            if self._on_cycle_complete:
                self._on_cycle_complete(cycle)

            # Step 6: Cooldown
            self.state = OrchestratorState.COOLDOWN

        except Exception as e:
            cycle.status = f"ERROR: {str(e)}"
            cycle.completed_at = datetime.utcnow()
            self.cycles.append(cycle)
            logger.error(f"Orchestration cycle {cycle.cycle_id} failed: {e}")

        self.state = OrchestratorState.IDLE
        return cycle

    # ─── Monitoring ─────────────────────────────────────────────

    def _monitor(self) -> List[OrchestrationSignal]:
        """Monitor all capital subsystems for signals."""
        signals = []

        if not self._intelligence:
            return signals

        # Efficiency signals
        efficiencies = self._intelligence.get_strategy_efficiencies()
        for sid, eff in efficiencies.items():
            if eff < self._min_efficiency_threshold:
                signals.append(OrchestrationSignal(
                    signal_type="LOW_EFFICIENCY",
                    severity="WARNING",
                    source=sid,
                    metric="capital_efficiency",
                    value=eff,
                    threshold=self._min_efficiency_threshold,
                    message=f"Strategy {sid} efficiency {eff:.4f} below threshold {self._min_efficiency_threshold}",
                ))

        # Concentration signals
        allocations = self._intelligence.get_strategy_allocations()
        total = sum(allocations.values())
        if total > 0:
            for sid, alloc in allocations.items():
                concentration = alloc / total
                if concentration > self._max_concentration:
                    signals.append(OrchestrationSignal(
                        signal_type="HIGH_CONCENTRATION",
                        severity="WARNING",
                        source=sid,
                        metric="concentration",
                        value=concentration,
                        threshold=self._max_concentration,
                        message=f"Strategy {sid} concentration {concentration:.2%} exceeds {self._max_concentration:.0%}",
                    ))

        # Utilization signals
        utilization = self._intelligence.get_utilization()
        if utilization > self._max_utilization:
            signals.append(OrchestrationSignal(
                signal_type="HIGH_UTILIZATION",
                severity="CRITICAL",
                source="capital_pool",
                metric="utilization",
                value=utilization,
                threshold=self._max_utilization,
                message=f"Capital utilization {utilization:.2%} exceeds {self._max_utilization:.0%}",
            ))
        elif utilization < self._min_utilization:
            signals.append(OrchestrationSignal(
                signal_type="LOW_UTILIZATION",
                severity="INFO",
                source="capital_pool",
                metric="utilization",
                value=utilization,
                threshold=self._min_utilization,
                message=f"Capital utilization {utilization:.2%} below {self._min_utilization:.0%}",
            ))

        # Correlation signals
        exposure = self._intelligence.get_exposure_matrix()
        for s1, correlations in exposure.items():
            for s2, corr in correlations.items():
                if s1 < s2 and abs(corr) > self._max_correlation:
                    signals.append(OrchestrationSignal(
                        signal_type="HIGH_CORRELATION",
                        severity="WARNING",
                        source=f"{s1}:{s2}",
                        metric="correlation",
                        value=abs(corr),
                        threshold=self._max_correlation,
                        message=f"High correlation {abs(corr):.2f} between {s1} and {s2}",
                    ))

        return signals

    # ─── Decision ───────────────────────────────────────────────

    def _should_act(self, signals: List[OrchestrationSignal]) -> bool:
        """Decide whether signals warrant action."""
        if not signals:
            return False

        # Must have at least one CRITICAL or multiple WARNING
        critical_count = sum(1 for s in signals if s.severity == "CRITICAL")
        warning_count = sum(1 for s in signals if s.severity == "WARNING")

        if critical_count > 0:
            return True
        if warning_count >= 2:
            return True

        return False

    def _can_act(self) -> bool:
        """Check if cooldown has elapsed."""
        if self._last_action_at is None:
            return True
        elapsed = (datetime.utcnow() - self._last_action_at).total_seconds()
        return elapsed >= self._cooldown_seconds

    # ─── Optimization ───────────────────────────────────────────

    def _optimize(self, signals: List[OrchestrationSignal]) -> Optional[Dict[str, Any]]:
        """Generate an allocation optimization proposal."""
        if not self._intelligence:
            return None

        # Extract constraints from signals
        constraints = {}
        for s in signals:
            if s.signal_type == "HIGH_CONCENTRATION":
                constraints[f"max_{s.source}"] = self._max_concentration

        # Determine objective based on dominant signal
        objective = "MAXIMIZE_SHARPE"
        if any(s.signal_type == "LOW_UTILIZATION" for s in signals):
            objective = "MAXIMIZE_UTILIZATION"
        elif any(s.signal_type == "HIGH_CORRELATION" for s in signals):
            objective = "MINIMIZE_CORRELATION"

        return self._intelligence.optimize_allocation(
            objective_type=objective,
            constraints=constraints,
        )

    # ─── Validation ─────────────────────────────────────────────

    def _validate_proposal(self, proposal: Dict[str, Any]) -> bool:
        """Validate proposal against guardrails."""
        if proposal.get("error"):
            return False

        # Check max reallocation percentage
        total_change = sum(
            abs(delta) for delta in proposal.get("deltas", {}).values()
        )
        total_capital = self._intelligence.get_total_capital() if self._intelligence else 1
        change_pct = total_change / total_capital if total_capital > 0 else 1.0

        if change_pct > self._max_reallocation_pct:
            logger.warning(f"Proposal rejected: change {change_pct:.2%} > max {self._max_reallocation_pct:.0%}")
            return False

        # Check minimum change amount
        if total_change < self._min_reallocation_amount:
            logger.debug(f"Proposal below minimum reallocation: {total_change}")
            return False

        return True

    # ─── Execution ──────────────────────────────────────────────

    def _execute_proposal(self, proposal: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute proposal through controller + manager."""
        actions = []
        deltas = proposal.get("deltas", {})

        for strategy_id, delta in deltas.items():
            if delta == 0:
                continue

            if self._controller and delta > 0:
                result = self._controller.allocate(strategy_id, abs(delta))
                actions.append({
                    "strategy": strategy_id,
                    "action": "allocate",
                    "amount": abs(delta),
                    "result": result.status,
                })
            elif self._controller and delta < 0:
                result = self._controller.deallocate(strategy_id, abs(delta))
                actions.append({
                    "strategy": strategy_id,
                    "action": "deallocate",
                    "amount": abs(delta),
                    "result": result.status,
                })

        return actions

    # ─── Background Loop ────────────────────────────────────────

    def start_background(self) -> None:
        """Start the orchestrator loop in a background thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("Orchestrator already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._background_loop,
            daemon=True,
            name=f"capital-orchestrator-{self.orchestrator_id}",
        )
        self._thread.start()
        logger.info(f"Orchestrator background loop started: {self.orchestrator_id}")

    def stop_background(self) -> None:
        """Stop the background loop."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=30)
        self.state = OrchestratorState.STOPPED
        logger.info(f"Orchestrator stopped: {self.orchestrator_id}")

    def _background_loop(self) -> None:
        """Background orchestration loop."""
        logger.info(f"Background loop started for {self.orchestrator_id}")
        while not self._stop_event.is_set():
            try:
                self.run_once(trigger=OrchestrationTrigger.SCHEDULED)
            except Exception as e:
                logger.error(f"Background cycle error: {e}")
            self._stop_event.wait(timeout=self._cycle_interval_seconds)

    # ─── Event-Driven Triggers ──────────────────────────────────

    def on_efficiency_drop(self, strategy_id: str, old_eff: float, new_eff: float) -> None:
        """Trigger when a strategy's efficiency drops."""
        if new_eff < self._min_efficiency_threshold and old_eff >= self._min_efficiency_threshold:
            logger.info(f"Efficiency drop triggered for {strategy_id}")
            self.run_once(trigger=OrchestrationTrigger.EFFICIENCY_THRESHOLD)

    def on_utilization_change(self, old_util: float, new_util: float) -> None:
        """Trigger when utilization crosses thresholds."""
        if old_util < self._max_utilization <= new_util:
            logger.info(f"Utilization breach triggered: {new_util:.2%}")
            self.run_once(trigger=OrchestrationTrigger.UTILIZATION_THRESHOLD)

    def on_concentration_alert(self, strategy_id: str, concentration: float) -> None:
        """Trigger when a strategy concentration exceeds limit."""
        if concentration > self._max_concentration:
            logger.warning(f"Concentration alert: {strategy_id} at {concentration:.2%}")
            self.run_once(trigger=OrchestrationTrigger.CONCENTRATION_ALERT)

    # ─── Helpers ────────────────────────────────────────────────

    def _empty_cycle(self, trigger: OrchestrationTrigger, status: str) -> OrchestrationCycle:
        return OrchestrationCycle(
            cycle_id=f"ocyc-{uuid.uuid4().hex[:8]}",
            trigger=trigger,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            status=status,
        )

    def get_summary(self) -> Dict[str, Any]:
        return {
            "orchestrator_id": self.orchestrator_id,
            "state": self.state.value,
            "cycles_completed": len(self.cycles),
            "last_action_at": self._last_action_at.isoformat() if self._last_action_at else None,
            "cooldown_remaining": max(
                0,
                self._cooldown_seconds - (
                    (datetime.utcnow() - self._last_action_at).total_seconds()
                    if self._last_action_at else self._cooldown_seconds
                ),
            ),
            "running": self._thread is not None and self._thread.is_alive(),
        }
