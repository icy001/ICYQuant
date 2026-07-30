"""Portfolio Agent - portfolio-level decision maker.

Responsible for portfolio composition decisions:
- Position sizing recommendations
- Rebalance proposals
- Cash management
- Sector allocation adjustments
- Risk-aware portfolio optimization

Works with Portfolio Management (Part 12) modules for execution.
"""

import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .agent_base import (
    BaseAgent, AgentStatus, Observation, Analysis, Decision, DecisionAction,
)

logger = logging.getLogger(__name__)


class RebalanceType(Enum):
    """Types of portfolio rebalance."""
    FULL = "full"
    PARTIAL = "partial"
    TACTICAL = "tactical"
    DRIFT = "drift"
    NONE = "none"


@dataclass
class RebalanceProposal:
    """A rebalance proposal for portfolio adjustment."""

    proposal_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    portfolio_id: str = ""
    rebalance_type: RebalanceType = RebalanceType.NONE
    target_weights: Dict[str, float] = field(default_factory=dict)
    current_weights: Dict[str, float] = field(default_factory=dict)
    trades: List[Dict[str, Any]] = field(default_factory=list)
    expected_turnover: float = 0.0
    estimated_cost: float = 0.0
    reason: str = ""
    confidence: float = 0.5
    timestamp: float = field(default_factory=time.time)
    status: str = "proposed"  # proposed, approved, rejected, executed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "portfolio_id": self.portfolio_id,
            "rebalance_type": self.rebalance_type.value,
            "target_weights": self.target_weights,
            "current_weights": self.current_weights,
            "trades": self.trades,
            "expected_turnover": self.expected_turnover,
            "estimated_cost": self.estimated_cost,
            "reason": self.reason,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "status": self.status,
        }


class PortfolioAgent(BaseAgent):
    """Portfolio Agent - portfolio-level decision making.

    Responsibilities:
    - Monitor portfolio composition and drift
    - Generate rebalance proposals
    - Cash management recommendations
    - Sector allocation oversight
    - Coordinate with Risk Agent for approval

    Communicates with:
    - Trading Agent (receives proposals)
    - Risk Agent (sends for approval)
    - Execution Agent (sends approved trades)
    """

    agent_type = "portfolio_agent"

    def __init__(self, name: str = None, config: Dict[str, Any] = None):
        super().__init__(name=name, config=config)
        self._portfolios: Dict[str, Dict[str, Any]] = {}
        self._current_weights: Dict[str, Dict[str, float]] = {}
        self._target_weights: Dict[str, Dict[str, float]] = {}
        self._rebalance_proposals: List[RebalanceProposal] = []
        self._drift_threshold = self.config.get("drift_threshold", 5.0)  # %
        self._max_turnover = self.config.get("max_turnover", 50.0)  # %
        self._cash_buffer_pct = self.config.get("cash_buffer_pct", 5.0)
        self._approved_trades: List[Dict[str, Any]] = []

        # Register message handlers
        self.communicator.register_handler("TRADE_PROPOSAL_NOTICE", self._on_trade_notice)
        self.communicator.register_handler("PORTFOLIO_STATE", self._on_portfolio_state)
        self.communicator.register_handler("MARKET_STATE", self._on_market_state)
        self.communicator.register_handler("RISK_DECISION", self._on_risk_decision)

    # ── Lifecycle ───────────────────────────────────────────────

    def start(self) -> None:
        super().start()
        self.memory.set_working("rebalance_count", 0)
        logger.info("PortfolioAgent [%s] started", self.name)

    # ── Message Handlers ────────────────────────────────────────

    def _on_trade_notice(self, data: Dict[str, Any]) -> None:
        """Handle trade proposal notice from Trading Agent."""
        proposal_id = data.get("decision_id", "")
        symbol = data.get("symbol", "")
        self.memory.set_working("latest_proposal", data)
        logger.debug("[%s] Notified of trade proposal: %s %s", self.name, symbol, proposal_id)

    def _on_portfolio_state(self, data: Dict[str, Any]) -> None:
        """Handle portfolio state update."""
        portfolio_id = data.get("portfolio_id", "default")
        self._portfolios[portfolio_id] = data
        weights = data.get("weights", {})
        if weights:
            self._current_weights[portfolio_id] = weights
        self.memory.set_working("portfolio_state", data)

    def _on_market_state(self, data: Dict[str, Any]) -> None:
        """Handle market state update."""
        self.memory.set_working("market_state", data)
        # Check if market conditions warrant portfolio review
        regime = data.get("regime", "unknown")
        if regime in ("risk_off", "crisis"):
            self.memory.set_working("portfolio_review_needed", True)

    def _on_risk_decision(self, data: Dict[str, Any]) -> None:
        """Handle risk agent decision on rebalance proposals."""
        proposal_id = data.get("proposal_id", "")
        decision = data.get("decision", "rejected")
        for p in self._rebalance_proposals:
            if p.proposal_id == proposal_id:
                p.status = decision
                if decision in ("approved", "approved_with_warnings"):
                    # Forward approved trades to Execution Agent
                    self.send_to(
                        recipient="execution_agent",
                        event="EXECUTE_TRADES",
                        data={
                            "proposal_id": proposal_id,
                            "portfolio_id": p.portfolio_id,
                            "trades": p.trades,
                            "rebalance_type": p.rebalance_type.value,
                        },
                    )
                break

    # ── Main Agent Loop ─────────────────────────────────────────

    def observe(self) -> Optional[Observation]:
        """Observe portfolio state and market conditions."""
        market_state = self.memory.get_working("market_state", {})
        review_needed = self.memory.get_working("portfolio_review_needed", False)

        return Observation(
            source=self.name,
            data={
                "portfolio_count": len(self._portfolios),
                "current_weights": dict(self._current_weights),
                "review_needed": review_needed,
                "market_regime": market_state.get("regime", "unknown"),
                "pending_rebalances": len([p for p in self._rebalance_proposals if p.status == "proposed"]),
                "approved_trades": len(self._approved_trades),
            },
            tags=["portfolio", "monitoring"],
        )

    def analyze(self, observation: Optional[Observation]) -> Optional[Analysis]:
        """Analyze portfolio health and identify adjustment needs."""
        if observation is None:
            return None

        data = observation.data
        signals = []
        confidence = 0.5

        # Check for drift in each portfolio
        for port_id, current_weights in self._current_weights.items():
            target = self._target_weights.get(port_id, {})
            if not target:
                continue

            drift_detected = False
            for symbol, target_w in target.items():
                current_w = current_weights.get(symbol, 0)
                drift = abs(current_w - target_w)
                if drift > self._drift_threshold:
                    drift_detected = True
                    signals.append({
                        "type": "DRIFT",
                        "portfolio": port_id,
                        "symbol": symbol,
                        "current": current_w,
                        "target": target_w,
                        "drift": drift,
                        "severity": "high" if drift > self._drift_threshold * 2 else "medium",
                    })

            if drift_detected:
                confidence = 0.7

        # Market regime adjustments
        market_regime = data.get("market_regime", "unknown")
        if market_regime in ("risk_off", "crisis", "trending_down"):
            signals.append({
                "type": "DEFENSIVE_ADJUSTMENT",
                "action": "INCREASE_CASH",
                "reason": f"Market regime: {market_regime}",
                "recommendation": f"Increase cash buffer to {self._cash_buffer_pct * 2:.0f}%",
            })
            confidence = 0.75

        elif market_regime in ("risk_on", "trending_up"):
            signals.append({
                "type": "OPPORTUNISTIC_ADJUSTMENT",
                "action": "DEPLOY_CASH",
                "reason": f"Market regime: {market_regime}",
                "recommendation": f"Reduce cash buffer to {max(1, self._cash_buffer_pct * 0.5):.0f}%",
            })
            confidence = 0.65

        # Review needed flag
        if data.get("review_needed"):
            signals.append({
                "type": "REVIEW_REQUIRED",
                "action": "FULL_REVIEW",
                "reason": "Portfolio review flagged by market conditions",
            })
            confidence = 0.8

        return Analysis(
            agent=self.name,
            summary=f"Portfolio review: {len(signals)} adjustment signal(s)",
            metrics={
                "portfolio_count": len(self._current_weights),
                "drift_detected": any(s["type"] == "DRIFT" for s in signals),
                "market_regime": market_regime,
            },
            signals=signals,
            confidence=confidence,
        )

    def decide(self, analysis: Optional[Analysis]) -> Optional[Decision]:
        """Generate rebalance proposals based on analysis."""
        if analysis is None or not analysis.signals:
            return Decision(
                agent=self.name,
                action=DecisionAction.HOLD,
                symbol="",
                confidence=0.5,
                reason=["Portfolio within tolerances"],
            )

        drift_signals = [s for s in analysis.signals if s["type"] == "DRIFT"]
        if drift_signals:
            # Generate rebalance proposal
            proposal = self._generate_rebalance_proposal(drift_signals)
            if proposal:
                self._rebalance_proposals.append(proposal)

                # Send to Risk Agent for approval
                self.send_to(
                    recipient="risk_agent",
                    event="REBALANCE_PROPOSAL",
                    data=proposal.to_dict(),
                )

                # Notify supervisor
                self.send_to(
                    recipient="supervisor",
                    event="REBALANCE_PROPOSED",
                    data={
                        "proposal_id": proposal.proposal_id,
                        "portfolio_id": proposal.portfolio_id,
                        "trades_count": len(proposal.trades),
                        "turnover": proposal.expected_turnover,
                    },
                )

                self.memory.set_working(
                    "rebalance_count",
                    self.memory.get_working("rebalance_count", 0) + 1,
                )

                return Decision(
                    agent=self.name,
                    action=DecisionAction.REBALANCE,
                    symbol="PORTFOLIO",
                    size=proposal.expected_turnover,
                    confidence=proposal.confidence,
                    reason=[proposal.reason],
                    metadata={"proposal_id": proposal.proposal_id},
                )

        # Defensive/opportunistic adjustments
        adjustment_signals = [s for s in analysis.signals if s["type"] in ("DEFENSIVE_ADJUSTMENT", "OPPORTUNISTIC_ADJUSTMENT")]
        if adjustment_signals:
            signal = adjustment_signals[0]
            action = DecisionAction.REDUCE if signal["type"] == "DEFENSIVE_ADJUSTMENT" else DecisionAction.INCREASE
            return Decision(
                agent=self.name,
                action=action,
                symbol="CASH",
                size=self._cash_buffer_pct,
                confidence=analysis.confidence,
                reason=[signal.get("recommendation", signal.get("reason", ""))],
            )

        return Decision(
            agent=self.name,
            action=DecisionAction.HOLD,
            symbol="",
            confidence=0.5,
            reason=["No rebalance needed"],
        )

    # ── Rebalance Logic ─────────────────────────────────────────

    def _generate_rebalance_proposal(
        self, drift_signals: List[Dict[str, Any]]
    ) -> Optional[RebalanceProposal]:
        """Generate a rebalance proposal from drift signals."""
        if not drift_signals:
            return None

        portfolio_id = drift_signals[0].get("portfolio", "default")
        current = self._current_weights.get(portfolio_id, {})
        target = self._target_weights.get(portfolio_id, {})

        trades = []
        total_turnover = 0.0

        for signal in drift_signals:
            symbol = signal["symbol"]
            cur_w = signal["current"]
            tgt_w = signal["target"]
            diff = tgt_w - cur_w

            if abs(diff) < 0.5:  # Minimum trade size
                continue

            trade = {
                "symbol": symbol,
                "action": "BUY" if diff > 0 else "SELL",
                "weight_change": diff,
                "current_weight": cur_w,
                "target_weight": tgt_w,
                "urgency": signal.get("severity", "medium"),
            }
            trades.append(trade)
            total_turnover += abs(diff)

        if not trades:
            return None

        # Cap turnover
        if total_turnover > self._max_turnover:
            scale = self._max_turnover / total_turnover
            for t in trades:
                t["weight_change"] *= scale
            total_turnover = self._max_turnover

        # Estimate cost (10 bps per trade)
        estimated_cost = len(trades) * 0.001

        return RebalanceProposal(
            portfolio_id=portfolio_id,
            rebalance_type=RebalanceType.DRIFT,
            target_weights=dict(target),
            current_weights=dict(current),
            trades=trades,
            expected_turnover=total_turnover,
            estimated_cost=estimated_cost,
            reason=f"Drift detected in {len(drift_signals)} position(s)",
            confidence=0.7,
        )

    # ── Portfolio Management Methods ────────────────────────────

    def set_target_weights(
        self, portfolio_id: str, weights: Dict[str, float]
    ) -> None:
        """Set target portfolio weights."""
        self._target_weights[portfolio_id] = weights
        self.memory.set_working(f"target_{portfolio_id}", weights)

    def get_current_weights(self, portfolio_id: str = "default") -> Dict[str, float]:
        """Get current portfolio weights."""
        return self._current_weights.get(portfolio_id, {})

    def calculate_drift(self, portfolio_id: str = "default") -> Dict[str, float]:
        """Calculate drift between current and target weights."""
        current = self._current_weights.get(portfolio_id, {})
        target = self._target_weights.get(portfolio_id, {})
        drift = {}
        for symbol in set(list(current.keys()) + list(target.keys())):
            drift[symbol] = current.get(symbol, 0) - target.get(symbol, 0)
        return drift

    def get_total_drift(self, portfolio_id: str = "default") -> float:
        """Get total absolute drift."""
        return sum(abs(d) for d in self.calculate_drift(portfolio_id).values())

    def approve_trade(self, trade_data: Dict[str, Any]) -> None:
        """Record an approved trade."""
        self._approved_trades.append({
            **trade_data,
            "approved_at": time.time(),
        })

    def get_proposals(
        self, status: str = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get rebalance proposals."""
        results = self._rebalance_proposals
        if status:
            results = [p for p in results if p.status == status]
        return [p.to_dict() for p in results[-limit:]]

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio summary."""
        return {
            "portfolio_count": len(self._portfolios),
            "current_weights": dict(self._current_weights),
            "target_weights": dict(self._target_weights),
            "total_drift": sum(self.get_total_drift(pid) for pid in self._current_weights),
            "pending_proposals": len([p for p in self._rebalance_proposals if p.status == "proposed"]),
            "approved_trades": len(self._approved_trades),
            "cash_buffer": self._cash_buffer_pct,
        }

    def get_status_report(self) -> Dict[str, Any]:
        report = super().get_status_report()
        report.update(self.get_portfolio_summary())
        return report
