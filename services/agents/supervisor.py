"""Agent Supervisor - AI investment committee coordinator.

The Supervisor acts as the "AI Investment Committee" that orchestrates:
- Market Agent → discovers opportunities
- Trading Agent → proposes trades
- Risk Agent → reviews and approves/rejects
- Portfolio Agent → adjusts composition
- Execution Agent → executes approved trades

The Supervisor manages the end-to-end decision pipeline and maintains
system-level oversight, including circuit breakers and escalation.
"""

import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .agent_base import BaseAgent, AgentStatus

logger = logging.getLogger(__name__)


class SystemMode(Enum):
    """Overall system operating mode."""
    NORMAL = "normal"
    CAUTIOUS = "cautious"
    DEFENSIVE = "defensive"
    HALTED = "halted"
    OBSERVE_ONLY = "observe_only"
    BACKTEST = "backtest"


class EscalationLevel(Enum):
    """Escalation levels for issues."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class AgentHeartbeat:
    """Heartbeat from an agent for health monitoring."""
    agent_name: str
    agent_type: str
    status: str = "unknown"
    last_activity: float = field(default_factory=time.time)
    errors: int = 0
    decisions_made: int = 0
    uptime_seconds: float = 0.0


@dataclass
class SystemEvent:
    """System-level event for audit trail."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    event_type: str = ""
    level: EscalationLevel = EscalationLevel.INFO
    source: str = ""
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "level": self.level.value,
            "source": self.source,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp,
        }


@dataclass
class PipelineRun:
    """A single end-to-end decision pipeline execution."""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: str = "initiated"  # initiated, observing, deciding, reviewing, executing, completed, failed
    market_observation: Optional[Dict[str, Any]] = None
    trade_proposal: Optional[Dict[str, Any]] = None
    risk_assessment: Optional[Dict[str, Any]] = None
    portfolio_adjustment: Optional[Dict[str, Any]] = None
    execution_result: Optional[Dict[str, Any]] = None
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "market_observation": self.market_observation,
            "trade_proposal": self.trade_proposal,
            "risk_assessment": self.risk_assessment,
            "portfolio_adjustment": self.portfolio_adjustment,
            "execution_result": self.execution_result,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration": (self.completed_at - self.started_at) if self.completed_at else None,
            "errors": self.errors,
        }


class Supervisor(BaseAgent):
    """Supervisor Agent - AI Investment Committee.

    Coordinates the full agent pipeline:
    1. Market Agent observes → finds opportunities
    2. Trading Agent analyzes → proposes trades
    3. Risk Agent reviews → approves/rejects
    4. Portfolio Agent adjusts → rebalances
    5. Execution Agent executes → fills orders

    The Supervisor ensures:
    - Correct pipeline ordering
    - System mode management (normal/cautious/defensive/halted)
    - Escalation handling
    - Health monitoring of all agents
    - Audit trail of all decisions
    """

    agent_type = "supervisor"

    def __init__(self, name: str = None, config: Dict[str, Any] = None):
        super().__init__(name=name or "supervisor", config=config)
        self._system_mode = SystemMode.NORMAL
        self._heartbeats: Dict[str, AgentHeartbeat] = {}
        self._events: List[SystemEvent] = []
        self._pipeline_runs: List[PipelineRun] = []
        self._active_run: Optional[PipelineRun] = None
        self._escalation_count: int = 0
        self._pipeline_count: int = 0
        self._agent_registry: Dict[str, BaseAgent] = {}

        # Configurable thresholds
        self._max_daily_escalations = self.config.get("max_daily_escalations", 10)
        self._heartbeat_timeout = self.config.get("heartbeat_timeout", 30)  # seconds
        self._max_pipeline_errors = self.config.get("max_pipeline_errors", 5)

        # Register message handlers
        self.communicator.register_handler("RISK_ESCALATION", self._on_risk_escalation)
        self.communicator.register_handler("RISK_ALERT", self._on_risk_alert)
        self.communicator.register_handler("EXECUTION_COMPLETE", self._on_execution_complete)
        self.communicator.register_handler("REBALANCE_PROPOSED", self._on_rebalance_proposed)
        self.communicator.register_handler("AGENT_HEARTBEAT", self._on_heartbeat)
        self.communicator.register_handler("MARKET_OBSERVATION", self._on_market_observation)
        self.communicator.register_handler("TRADE_DECISION", self._on_trade_decision)

    # ── Lifecycle ───────────────────────────────────────────────

    def start(self) -> None:
        super().start()
        self.log_event("system", "Supervisor started", EscalationLevel.INFO)
        logger.info("Supervisor [%s] started in %s mode", self.name, self._system_mode.value)

    def register_agent(self, agent: BaseAgent) -> None:
        """Register an agent under supervisor management."""
        self._agent_registry[agent.agent_type] = agent
        logger.info("[%s] Registered agent: %s (%s)", self.name, agent.name, agent.agent_type)

    # ── Message Handlers ────────────────────────────────────────

    def _on_heartbeat(self, data: Dict[str, Any]) -> None:
        """Handle agent heartbeat."""
        agent_name = data.get("agent_name", "unknown")
        self._heartbeats[agent_name] = AgentHeartbeat(
            agent_name=agent_name,
            agent_type=data.get("agent_type", "unknown"),
            status=data.get("status", "unknown"),
            last_activity=data.get("last_activity", time.time()),
            errors=data.get("errors", 0),
            decisions_made=data.get("decisions_made", 0),
            uptime_seconds=data.get("uptime_seconds", 0),
        )

    def _on_market_observation(self, data: Dict[str, Any]) -> None:
        """Handle market observation from Market Agent."""
        if self._active_run:
            self._active_run.market_observation = data
            self._active_run.status = "observing"
        logger.info("[%s] Received market observation: regime=%s", self.name, data.get("regime", "unknown"))

    def _on_trade_decision(self, data: Dict[str, Any]) -> None:
        """Handle trade decision from Trading Agent."""
        if self._active_run:
            self._active_run.trade_proposal = data
            self._active_run.status = "deciding"

    def _on_risk_escalation(self, data: Dict[str, Any]) -> None:
        """Handle risk escalation from Risk Agent."""
        self._escalation_count += 1
        summary = data.get("summary", "No details")
        risks = data.get("risks", [])
        high_risks = [r for r in risks if r.get("severity") == "high"]

        event_level = EscalationLevel.CRITICAL if high_risks else EscalationLevel.WARNING
        self.log_event("risk", summary, event_level, data)

        # Auto-halt on critical risks
        if high_risks and self._system_mode != SystemMode.HALTED:
            self._system_mode = SystemMode.HALTED
            self.log_event(
                "system",
                "System HALTED due to critical risk escalation",
                EscalationLevel.EMERGENCY,
                {"risks": high_risks},
            )
            # Broadcast halt to all agents
            self.communicator.broadcast(
                event="SYSTEM_HALT",
                data={
                    "reason": "Critical risk escalation",
                    "risks": high_risks,
                    "supervisor": self.name,
                },
            )

        # Check escalation threshold
        if self._escalation_count >= self._max_daily_escalations:
            self._system_mode = SystemMode.CAUTIOUS
            self.log_event(
                "system",
                f"Switched to CAUTIOUS mode: {self._escalation_count} escalations",
                EscalationLevel.WARNING,
            )

    def _on_risk_alert(self, data: Dict[str, Any]) -> None:
        """Handle risk alert (rejected trade proposals)."""
        if self._active_run:
            self._active_run.risk_assessment = data
            self._active_run.status = "reviewing"

        decision = data.get("decision", "unknown")
        if decision in ("rejected", "blocked"):
            self.log_event(
                "risk",
                f"Trade {data.get('proposal_id')}: {decision} - {data.get('reason')}",
                EscalationLevel.WARNING,
                data,
            )

    def _on_rebalance_proposed(self, data: Dict[str, Any]) -> None:
        """Handle rebalance proposal from Portfolio Agent."""
        if self._active_run:
            self._active_run.portfolio_adjustment = data
            self._active_run.status = "reviewing"

    def _on_execution_complete(self, data: Dict[str, Any]) -> None:
        """Handle execution completion from Execution Agent."""
        if self._active_run:
            self._active_run.execution_result = data
            self._active_run.status = "completed"
            self._active_run.completed_at = time.time()
            self._pipeline_runs.append(self._active_run)
            self._pipeline_count += 1
            self._active_run = None

            # Learn from completed pipeline
            self.memory.learn_from_outcome(
                decision={"pipeline_completed": True},
                outcome="success",
                reward=1.0,
                context={"pipeline_count": self._pipeline_count},
            )

        logger.info("[%s] Pipeline execution complete", self.name)

    # ── Main Agent Loop ─────────────────────────────────────────

    def observe(self) -> Optional[Dict[str, Any]]:
        """Observe system state and agent health."""
        from services.agents.agent_base import Observation

        # Check agent health
        unhealthy_agents = []
        now = time.time()
        for name, hb in self._heartbeats.items():
            if now - hb.last_activity > self._heartbeat_timeout:
                unhealthy_agents.append({
                    "name": name,
                    "type": hb.agent_type,
                    "last_seen": hb.last_activity,
                    "seconds_ago": now - hb.last_activity,
                })

        return Observation(
            source=self.name,
            data={
                "system_mode": self._system_mode.value,
                "agent_count": len(self._heartbeats),
                "unhealthy_agents": unhealthy_agents,
                "escalation_count": self._escalation_count,
                "pipeline_count": self._pipeline_count,
                "active_pipeline": self._active_run is not None,
            },
            tags=["supervisor", "system"],
        )

    def analyze(self, observation: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Analyze system health and determine if mode change needed."""
        from services.agents.agent_base import Analysis

        if observation is None:
            return None

        data = observation.data
        signals = []
        confidence = 0.8

        # Check for unhealthy agents
        unhealthy = data.get("unhealthy_agents", [])
        if unhealthy:
            for agent in unhealthy:
                signals.append({
                    "type": "AGENT_UNHEALTHY",
                    "agent": agent["name"],
                    "severity": "high",
                    "recommendation": "restart_or_alert",
                })
            confidence = 0.5

        # Check escalation count
        if self._escalation_count > self._max_daily_escalations * 0.8:
            signals.append({
                "type": "ESCALATION_THRESHOLD",
                "count": self._escalation_count,
                "limit": self._max_daily_escalations,
                "severity": "medium",
                "recommendation": "review_risk_policies",
            })

        return Analysis(
            agent=self.name,
            summary=f"System: {data.get('system_mode')}, {data.get('agent_count')} agents",
            metrics={
                "unhealthy": len(unhealthy),
                "escalations": self._escalation_count,
                "pipelines": self._pipeline_count,
            },
            signals=signals,
            confidence=confidence,
        )

    def decide(self, analysis: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Supervisor decision - mode management and health response."""
        from services.agents.agent_base import Decision, DecisionAction

        if analysis is None:
            return Decision(
                agent=self.name,
                action=DecisionAction.HOLD,
                symbol="",
                confidence=0.8,
                reason=["System monitoring"],
            )

        signals = analysis.signals
        if not signals:
            return Decision(
                agent=self.name,
                action=DecisionAction.HOLD,
                symbol="",
                confidence=0.8,
                reason=["System healthy"],
            )

        # Handle unhealthy agents
        unhealthy_signals = [s for s in signals if s["type"] == "AGENT_UNHEALTHY"]
        if unhealthy_signals and self._system_mode == SystemMode.NORMAL:
            self._system_mode = SystemMode.CAUTIOUS
            self.log_event(
                "system",
                f"Switched to CAUTIOUS: {len(unhealthy_signals)} agent(s) unhealthy",
                EscalationLevel.WARNING,
            )
            return Decision(
                agent=self.name,
                action=DecisionAction.HOLD,
                symbol="",
                confidence=0.5,
                reason=[f"Mode change to {self._system_mode.value}"],
            )

        return Decision(
            agent=self.name,
            action=DecisionAction.HOLD,
            symbol="",
            confidence=0.7,
            reason=["Monitoring system health"],
        )

    # ── Pipeline Orchestration ──────────────────────────────────

    def run_pipeline(self, symbols: List[str] = None) -> PipelineRun:
        """Execute a full decision pipeline."""
        if self._system_mode == SystemMode.HALTED:
            run = PipelineRun(status="failed")
            run.errors.append("System is HALTED")
            return run

        if self._active_run:
            return self._active_run  # Already running

        run = PipelineRun()
        self._active_run = run
        symbols = symbols or []

        logger.info("[%s] Starting pipeline run %s for %d symbols", self.name, run.run_id, len(symbols))

        # Step 1: Request market observation
        self.send_to(
            recipient="market_agent",
            event="SCAN_MARKET",
            data={
                "run_id": run.run_id,
                "symbols": symbols,
                "mode": self._system_mode.value,
            },
        )
        run.status = "observing"

        return run

    def get_active_pipeline(self) -> Optional[Dict[str, Any]]:
        """Get current active pipeline run."""
        if self._active_run:
            return self._active_run.to_dict()
        return None

    def get_pipeline_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent pipeline runs."""
        return [p.to_dict() for p in self._pipeline_runs[-limit:]]

    # ── System Mode Management ──────────────────────────────────

    def set_mode(self, mode: SystemMode) -> None:
        """Set system operating mode."""
        old_mode = self._system_mode
        self._system_mode = mode
        self.log_event(
            "system",
            f"Mode changed: {old_mode.value} → {mode.value}",
            EscalationLevel.WARNING if mode in (SystemMode.HALTED, SystemMode.DEFENSIVE) else EscalationLevel.INFO,
        )
        # Broadcast mode change
        self.communicator.broadcast(
            event="MODE_CHANGE",
            data={
                "old_mode": old_mode.value,
                "new_mode": mode.value,
                "supervisor": self.name,
            },
        )

    def get_mode(self) -> SystemMode:
        """Get current system mode."""
        return self._system_mode

    # ── Event Logging ───────────────────────────────────────────

    def log_event(
        self,
        event_type: str,
        message: str,
        level: EscalationLevel,
        data: Dict[str, Any] = None,
    ) -> SystemEvent:
        """Log a system event."""
        event = SystemEvent(
            event_type=event_type,
            level=level,
            source=self.name,
            message=message,
            data=data or {},
        )
        self._events.append(event)

        # Keep event log bounded
        if len(self._events) > 1000:
            self._events = self._events[-1000:]

        # Log to memory for learning
        if level in (EscalationLevel.CRITICAL, EscalationLevel.EMERGENCY):
            self.memory.remember_episode(
                content=event.to_dict(),
                context={"type": event_type},
                tags=["escalation", level.value],
            )

        return event

    def get_events(
        self,
        level: EscalationLevel = None,
        event_type: str = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get system events with optional filters."""
        results = self._events
        if level:
            results = [e for e in results if e.level == level]
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        return [e.to_dict() for e in results[-limit:]]

    # ── Health & Status ─────────────────────────────────────────

    def check_agent_health(self) -> Dict[str, Any]:
        """Check health of all registered agents."""
        now = time.time()
        health = {}
        for name, hb in self._heartbeats.items():
            stale = now - hb.last_activity > self._heartbeat_timeout
            health[name] = {
                "status": hb.status,
                "healthy": not stale,
                "last_activity_ago": now - hb.last_activity,
                "decisions": hb.decisions_made,
                "errors": hb.errors,
                "uptime": hb.uptime_seconds,
            }
        return health

    def get_system_summary(self) -> Dict[str, Any]:
        """Get full system summary."""
        return {
            "system_mode": self._system_mode.value,
            "agents": self.check_agent_health(),
            "escalation_count": self._escalation_count,
            "pipeline_count": self._pipeline_count,
            "active_pipeline": self.get_active_pipeline(),
            "events_today": len(self._events),
        }

    def get_status_report(self) -> Dict[str, Any]:
        report = super().get_status_report()
        report.update(self.get_system_summary())
        return report
