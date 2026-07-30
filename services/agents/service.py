"""Agent Service - unified service layer for AI Trading Agents.

Orchestrates all agents, decision engine, and workflow engine.
Provides a clean service API for external consumers.
"""

import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .market_agent import MarketAgent
from .trading_agent import TradingAgent
from .risk_agent import RiskAgent
from .portfolio_agent import PortfolioAgent
from .execution_agent import ExecutionAgent
from .supervisor import Supervisor, SystemMode
from .decision import DecisionEngine, DecisionInput, FinalDecision
from .workflow import WorkflowEngine
from .communication import AgentCommunicator
from .policy import PolicyEngine

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service operational status."""
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ServiceConfig:
    """Agent service configuration."""
    name: str = "agent_service"
    auto_start: bool = True
    enable_market_agent: bool = True
    enable_trading_agent: bool = True
    enable_risk_agent: bool = True
    enable_portfolio_agent: bool = True
    enable_execution_agent: bool = True
    enable_supervisor: bool = True
    enable_workflow: bool = True
    decision_weights: Dict[str, float] = field(default_factory=dict)
    heartbeat_interval: float = 5.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentService:
    """Unified Agent Service - orchestrates all AI trading agents.

    Usage:
        service = AgentService()
        service.start()
        result = service.request_decision("NVDA")
        service.stop()
    """

    def __init__(self, config: ServiceConfig = None):
        self.config = config or ServiceConfig()
        self.status = ServiceStatus.INITIALIZED

        # Core engines
        self.decision_engine = DecisionEngine(
            config={"weight_market": 0.25, "weight_trading": 0.25,
                    "weight_risk": 0.30, "weight_portfolio": 0.15,
                    "weight_execution": 0.05}
        )
        self.workflow_engine = WorkflowEngine()
        self.policy_engine = PolicyEngine.create_default_engine()

        # Agents
        self.market_agent: Optional[MarketAgent] = None
        self.trading_agent: Optional[TradingAgent] = None
        self.risk_agent: Optional[RiskAgent] = None
        self.portfolio_agent: Optional[PortfolioAgent] = None
        self.execution_agent: Optional[ExecutionAgent] = None
        self.supervisor: Optional[Supervisor] = None

        # Statistics
        self._started_at: Optional[float] = None
        self._decision_count: int = 0

    # ── Lifecycle ───────────────────────────────────────────────

    def start(self) -> None:
        """Start the agent service and all enabled agents."""
        self.status = ServiceStatus.STARTING
        self._started_at = time.time()

        logger.info("Starting Agent Service...")

        # Create agents based on config
        if self.config.enable_market_agent:
            self.market_agent = MarketAgent(name="market_agent")
            self.market_agent.start()

        if self.config.enable_trading_agent:
            self.trading_agent = TradingAgent(name="trading_agent")
            self.trading_agent.start()

        if self.config.enable_risk_agent:
            self.risk_agent = RiskAgent(name="risk_agent")
            self.risk_agent.start()

        if self.config.enable_portfolio_agent:
            self.portfolio_agent = PortfolioAgent(name="portfolio_agent")
            self.portfolio_agent.start()

        if self.config.enable_execution_agent:
            self.execution_agent = ExecutionAgent(name="execution_agent")
            self.execution_agent.start()

        if self.config.enable_supervisor:
            self.supervisor = Supervisor(name="supervisor")
            # Register all agents with supervisor
            for agent in [self.market_agent, self.trading_agent, self.risk_agent,
                          self.portfolio_agent, self.execution_agent]:
                if agent:
                    self.supervisor.register_agent(agent)
            self.supervisor.start()

        # Wire up workflow engine send function
        self.workflow_engine.set_send_function(self._send_to_agent)

        self.status = ServiceStatus.RUNNING
        logger.info("Agent Service started with %d agents", len(self._get_active_agents()))

    def stop(self) -> None:
        """Stop the agent service and all agents."""
        self.status = ServiceStatus.STOPPING
        logger.info("Stopping Agent Service...")

        for agent in self._get_active_agents():
            try:
                agent.stop()
            except Exception as e:
                logger.error("Error stopping %s: %s", agent.name, e)

        self.status = ServiceStatus.STOPPED
        logger.info("Agent Service stopped")

    def pause(self) -> None:
        """Pause all agent activity."""
        if self.supervisor:
            self.supervisor.set_mode(SystemMode.OBSERVE_ONLY)
        self.status = ServiceStatus.PAUSED

    def resume(self) -> None:
        """Resume agent activity."""
        if self.supervisor:
            self.supervisor.set_mode(SystemMode.NORMAL)
        self.status = ServiceStatus.RUNNING

    def _get_active_agents(self) -> List:
        """Get list of active agents."""
        agents = [
            self.market_agent, self.trading_agent, self.risk_agent,
            self.portfolio_agent, self.execution_agent, self.supervisor,
        ]
        return [a for a in agents if a is not None]

    def _send_to_agent(self, recipient: str, event: str, data: Dict[str, Any]) -> None:
        """Send message to a specific agent by type."""
        agent_map = {
            "market_agent": self.market_agent,
            "trading_agent": self.trading_agent,
            "risk_agent": self.risk_agent,
            "portfolio_agent": self.portfolio_agent,
            "execution_agent": self.execution_agent,
            "supervisor": self.supervisor,
        }
        agent = agent_map.get(recipient)
        if agent:
            agent.communicator._dispatch(event, data)

    # ── Decision API ────────────────────────────────────────────

    def request_decision(self, symbol: str) -> Dict[str, Any]:
        """Request an AI trading decision for a symbol.

        Runs the full pipeline: Market → Trading → Risk → Decision.

        Args:
            symbol: Trading symbol (e.g., "NVDA")

        Returns:
            Decision output with action, confidence, risk assessment
        """
        # 1. Market observation
        market_data = None
        if self.market_agent:
            observation = self.market_agent.observe()
            if observation:
                market_data = observation.data

        # 2. Trading proposal
        trade_data = None
        if self.trading_agent:
            self.trading_agent.update_market_data({symbol: market_data or {}})
            decision = self.trading_agent.decide(
                self.trading_agent.analyze(
                    self.trading_agent.observe()
                )
            )
            if decision:
                trade_data = {
                    "decision_id": decision.decision_id,
                    "symbol": decision.symbol or symbol,
                    "action": decision.action.value if hasattr(decision.action, 'value') else str(decision.action),
                    "confidence": decision.confidence,
                    "size": decision.size,
                    "reason": decision.reason,
                }

        # 3. Risk assessment
        risk_data = None
        if self.risk_agent and trade_data:
            assessment = self.risk_agent.evaluate_proposal(
                proposal_id=trade_data.get("decision_id", ""),
                symbol=symbol,
                action=trade_data.get("action", "HOLD"),
                size_pct=trade_data.get("size", 2.0),
                confidence=trade_data.get("confidence", 0.5),
            )
            risk_data = assessment.to_dict()

        # 4. Final decision via Decision Engine
        inputs = DecisionInput(
            market_signal=market_data,
            trade_proposal=trade_data,
            risk_assessment=risk_data,
        )
        output = self.decision_engine.decide(inputs)
        self._decision_count += 1

        return output.to_dict()

    def request_portfolio_review(self, portfolio_id: str = "default") -> Dict[str, Any]:
        """Request a portfolio review from the Portfolio Agent."""
        if not self.portfolio_agent:
            return {"error": "Portfolio Agent not enabled"}

        summary = self.portfolio_agent.get_portfolio_summary()
        drift = self.portfolio_agent.calculate_drift(portfolio_id)
        total_drift = sum(abs(d) for d in drift.values())

        return {
            "portfolio_id": portfolio_id,
            "total_drift": total_drift,
            "drift": drift,
            "drift_threshold": self.portfolio_agent._drift_threshold,
            "needs_rebalance": total_drift > self.portfolio_agent._drift_threshold,
            "summary": summary,
        }

    def request_risk_check(self, metrics: Dict[str, Any] = None) -> Dict[str, Any]:
        """Request a risk check with optional metrics."""
        if not self.risk_agent:
            return {"error": "Risk Agent not enabled"}

        if metrics:
            self.risk_agent.update_risk_metrics(metrics)

        return {
            "summary": self.risk_agent.get_risk_summary(),
            "policy_status": self.policy_engine.get_status(),
            "circuit_breaker": self.policy_engine.is_circuit_breaker_active(),
        }

    # ── Workflow API ────────────────────────────────────────────

    def start_workflow(self, name: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Start a named workflow."""
        run = self.workflow_engine.start_workflow(name, context)
        if run:
            return {"run_id": run.run_id, "status": run.status.value}
        return {"error": f"Workflow '{name}' not found"}

    def get_workflow_status(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a workflow run."""
        return self.workflow_engine.get_workflow_status(run_id)

    def cancel_workflow(self, run_id: str) -> Dict[str, Any]:
        """Cancel a running workflow."""
        cancelled = self.workflow_engine.cancel_workflow(run_id)
        return {"cancelled": cancelled}

    # ── System API ──────────────────────────────────────────────

    def get_system_status(self) -> Dict[str, Any]:
        """Get full system status."""
        agent_statuses = {}
        for agent in self._get_active_agents():
            agent_statuses[agent.agent_type] = {
                "name": agent.name,
                "status": agent.status.value,
                "decisions_made": agent.decision_count if hasattr(agent, 'decision_count') else 0,
            }

        return {
            "service_status": self.status.value,
            "uptime_seconds": time.time() - (self._started_at or time.time()),
            "agents": agent_statuses,
            "decisions_total": self._decision_count,
            "system_mode": self.supervisor.get_mode().value if self.supervisor else "unknown",
            "workflows": self.workflow_engine.get_summary() if self.config.enable_workflow else {},
            "policy_engine": self.policy_engine.get_status(),
        }

    def get_agent_logs(self, agent_type: str = None, limit: int = 50) -> Dict[str, Any]:
        """Get agent decision logs for explainability.

        Args:
            agent_type: Filter by agent type (optional)
            limit: Maximum log entries
        """
        logs = {}

        agents_to_query = self._get_active_agents()
        if agent_type:
            agents_to_query = [a for a in agents_to_query if a.agent_type == agent_type]

        for agent in agents_to_query:
            agent_logs = []
            # Get decisions if agent has them
            if hasattr(agent, 'get_decisions'):
                agent_logs = agent.get_decisions(limit=limit)
            elif hasattr(agent, 'get_assessments'):
                agent_logs = agent.get_assessments(limit=limit)
            elif hasattr(agent, 'get_orders'):
                agent_logs = agent.get_orders(limit=limit)

            if agent_logs:
                logs[agent.agent_type] = agent_logs

        return {
            "total_entries": sum(len(v) for v in logs.values()),
            "by_agent": logs,
        }

    def get_decision_reasons(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed reasons for a specific decision (explainability)."""
        decision = self.decision_engine.get_decision(decision_id)
        if not decision:
            return None

        return {
            "decision_id": decision_id,
            "decision": decision.get("decision"),
            "action": decision.get("action"),
            "reasons": decision.get("reasons", []),
            "warnings": decision.get("warnings", []),
            "scores": decision.get("scores", {}),
            "weights": decision.get("weights", {}),
            "composite_score": decision.get("composite_score"),
            "confidence": decision.get("confidence"),
        }

    # ── Agent Management ────────────────────────────────────────

    def set_system_mode(self, mode: str) -> Dict[str, Any]:
        """Set the system operating mode."""
        if not self.supervisor:
            return {"error": "Supervisor not enabled"}

        mode_map = {
            "normal": SystemMode.NORMAL,
            "cautious": SystemMode.CAUTIOUS,
            "defensive": SystemMode.DEFENSIVE,
            "halted": SystemMode.HALTED,
            "observe_only": SystemMode.OBSERVE_ONLY,
            "backtest": SystemMode.BACKTEST,
        }

        target_mode = mode_map.get(mode.lower())
        if not target_mode:
            return {"error": f"Invalid mode: {mode}. Valid: {list(mode_map.keys())}"}

        self.supervisor.set_mode(target_mode)
        return {"mode": target_mode.value, "status": "ok"}

    def update_decision_weights(self, weights: Dict[str, float]) -> Dict[str, Any]:
        """Update decision engine weights."""
        self.decision_engine.update_weights(weights)
        return {"weights": self.decision_engine._weights, "status": "ok"}

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive service summary."""
        return {
            "status": self.status.value,
            "agents": len(self._get_active_agents()),
            "decisions": self._decision_count,
            "decision_engine": self.decision_engine.get_summary(),
            "workflows": self.workflow_engine.get_summary(),
            "system_mode": self.supervisor.get_mode().value if self.supervisor else "N/A",
            "uptime": time.time() - (self._started_at or time.time()),
        }
