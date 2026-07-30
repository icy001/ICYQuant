"""Risk Agent - AI risk controller for autonomous trading.

Responsible for reviewing all trade proposals before execution:
- Position limit checks
- Sector exposure limits
- VaR (Value at Risk) analysis
- Drawdown monitoring
- Liquidity risk assessment
- Concentration risk
- Leverage limits

Every Trading Agent proposal MUST pass Risk Agent approval.
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
from .policy import PolicyEngine, PolicyAction

logger = logging.getLogger(__name__)


class RiskDecision(Enum):
    """Risk review outcome."""
    APPROVED = "approved"
    APPROVED_WITH_WARNINGS = "approved_with_warnings"
    SIZE_REDUCED = "size_reduced"
    REJECTED = "rejected"
    BLOCKED = "blocked"


@dataclass
class RiskAssessment:
    """Full risk assessment of a trade proposal."""

    assessment_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    proposal_id: str = ""
    symbol: str = ""
    action: str = ""
    decision: RiskDecision = RiskDecision.APPROVED
    original_size: float = 0.0
    approved_size: float = 0.0
    confidence: float = 0.5
    risk_score: float = 0.0  # 0=no risk, 1=maximum risk
    checks: List[Dict[str, Any]] = field(default_factory=list)
    violations: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    reason: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "proposal_id": self.proposal_id,
            "symbol": self.symbol,
            "action": self.action,
            "decision": self.decision.value,
            "original_size": self.original_size,
            "approved_size": self.approved_size,
            "confidence": self.confidence,
            "risk_score": self.risk_score,
            "checks": self.checks,
            "violations": self.violations,
            "warnings": self.warnings,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


class RiskAgent(BaseAgent):
    """Risk Agent - AI-powered risk control.

    Evaluates every trade proposal against:
    - Policy rules (position limits, sector exposure, etc.)
    - Current portfolio state
    - Market conditions (volatility, liquidity)
    - Historical performance and drawdowns

    Can approve, warn, reduce size, reject, or block trades.
    """

    agent_type = "risk_agent"

    def __init__(self, name: str = None, config: Dict[str, Any] = None):
        super().__init__(name=name, config=config)
        self.policy_engine = PolicyEngine.create_default_engine()
        self._assessments: List[RiskAssessment] = []
        self._rejected_proposals: List[Dict[str, Any]] = []
        self._risk_metrics: Dict[str, Any] = {
            "current_drawdown_pct": 0.0,
            "daily_pnl_pct": 0.0,
            "var_95": 0.0,
            "leverage": 1.0,
            "trades_this_hour": 0,
            "top_holding_pct": 0.0,
        }
        self._sector_exposures: Dict[str, float] = {}
        self._position_sizes: Dict[str, float] = {}
        self._approval_count = 0
        self._rejection_count = 0

        # Register message handlers
        self.communicator.register_handler("TRADE_PROPOSAL", self._on_trade_proposal)
        self.communicator.register_handler("PORTFOLIO_STATE", self._on_portfolio_state)
        self.communicator.register_handler("MARKET_STATE", self._on_market_state)

    # ── Lifecycle ───────────────────────────────────────────────

    def start(self) -> None:
        super().start()
        self.memory.set_working("approvals", 0)
        self.memory.set_working("rejections", 0)
        logger.info("RiskAgent [%s] started with %d policy rules",
                    self.name, len(self.policy_engine._rules))

    # ── Message Handlers ────────────────────────────────────────

    def _on_trade_proposal(self, data: Dict[str, Any]) -> None:
        """Handle incoming trade proposal from Trading Agent."""
        proposal_id = data.get("decision_id", "")
        symbol = data.get("symbol", "")
        action = data.get("action", "")
        size = data.get("size", 0.0)
        confidence = data.get("confidence", 0.5)

        assessment = self.evaluate_proposal(proposal_id, symbol, action, size, confidence)

        # Respond to Trading Agent
        self.send_to(
            recipient="trading_agent",
            event="RISK_DECISION",
            data={
                "proposal_id": proposal_id,
                "decision": assessment.decision.value,
                "approved_size": assessment.approved_size,
                "risk_score": assessment.risk_score,
                "reason": assessment.reason,
                "warnings": assessment.warnings,
            },
        )

        # Notify Supervisor of risk decisions
        if assessment.decision in (RiskDecision.REJECTED, RiskDecision.BLOCKED):
            self.send_to(
                recipient="supervisor",
                event="RISK_ALERT",
                data={
                    "proposal_id": proposal_id,
                    "symbol": symbol,
                    "action": action,
                    "decision": assessment.decision.value,
                    "reason": assessment.reason,
                },
            )

        logger.info(
            "[%s] Proposal %s: %s %s %s -> %s (risk=%.2f)",
            self.name, proposal_id, action, symbol,
            f"{size:.1f}%", assessment.decision.value, assessment.risk_score,
        )

    def _on_portfolio_state(self, data: Dict[str, Any]) -> None:
        """Handle portfolio state update."""
        self._risk_metrics.update(data.get("risk_metrics", {}))
        self._sector_exposures = data.get("sector_exposures", {})
        self._position_sizes = data.get("position_sizes", {})
        self.memory.set_working("portfolio_state", data)

    def _on_market_state(self, data: Dict[str, Any]) -> None:
        """Handle market state update for risk context."""
        self.memory.set_working("market_state", data)
        volatility = data.get("volatility", "medium")
        # Adjust risk tolerance based on market conditions
        if volatility in ("high", "extreme"):
            self.memory.set_working("risk_mode", "conservative")
        elif data.get("regime") == "risk_off":
            self.memory.set_working("risk_mode", "defensive")
        else:
            self.memory.set_working("risk_mode", "normal")

    # ── Main Agent Loop ─────────────────────────────────────────

    def observe(self) -> Optional[Observation]:
        """Monitor risk metrics and portfolio state."""
        return Observation(
            source=self.name,
            data={
                "risk_metrics": dict(self._risk_metrics),
                "sector_exposures": dict(self._sector_exposures),
                "position_count": len(self._position_sizes),
                "pending_assessments": len([a for a in self._assessments if a.decision == RiskDecision.APPROVED]),
                "circuit_breaker": self.policy_engine.is_circuit_breaker_active(),
            },
            tags=["risk", "monitoring"],
        )

    def analyze(self, observation: Optional[Observation]) -> Optional[Analysis]:
        """Analyze risk posture and identify emerging risks."""
        if observation is None:
            return None

        data = observation.data
        metrics = data.get("risk_metrics", {})

        risks = []
        confidence = 0.8

        # Check drawdown
        dd = abs(metrics.get("current_drawdown_pct", 0))
        if dd > 7.0:
            risks.append({
                "type": "DRAWDOWN",
                "severity": "high" if dd > 10.0 else "medium",
                "value": dd,
                "recommendation": "reduce_exposure",
            })
            confidence = 0.6

        # Check daily loss
        daily_pnl = metrics.get("daily_pnl_pct", 0)
        if daily_pnl < -2.0:
            risks.append({
                "type": "DAILY_LOSS",
                "severity": "high" if daily_pnl < -3.0 else "medium",
                "value": daily_pnl,
                "recommendation": "halt_trading" if daily_pnl < -3.0 else "reduce",
            })
            confidence = 0.5

        # Check VaR
        var_95 = abs(metrics.get("var_95", 0))
        if var_95 > 0.05:
            risks.append({
                "type": "VAR_BREACH",
                "severity": "medium",
                "value": var_95,
                "recommendation": "hedge_or_reduce",
            })

        # Check leverage
        leverage = metrics.get("leverage", 1.0)
        if leverage > 1.0:
            risks.append({
                "type": "LEVERAGE",
                "severity": "high",
                "value": leverage,
                "recommendation": "deleverage",
            })

        summary = "Risk posture normal"
        if risks:
            high_risks = [r for r in risks if r["severity"] == "high"]
            if high_risks:
                summary = f"CRITICAL: {len(high_risks)} high-severity risks detected"
            else:
                summary = f"WARNING: {len(risks)} risk(s) detected"

        return Analysis(
            agent=self.name,
            summary=summary,
            metrics={
                "risk_count": len(risks),
                "circuit_breaker": self.policy_engine.is_circuit_breaker_active(),
                "approvals": self._approval_count,
                "rejections": self._rejection_count,
            },
            signals=risks,
            confidence=confidence,
        )

    def decide(self, analysis: Optional[Analysis]) -> Optional[Decision]:
        """Risk agent's own decision - risk posture adjustment recommendations."""
        if analysis is None:
            return Decision(
                agent=self.name,
                action=DecisionAction.HOLD,
                symbol="",
                confidence=0.8,
                reason=["Risk monitoring only - no action needed"],
            )

        risks = analysis.signals
        if not risks:
            return Decision(
                agent=self.name,
                action=DecisionAction.HOLD,
                symbol="",
                confidence=0.8,
                reason=["Risk levels acceptable"],
            )

        high_risks = [r for r in risks if r["severity"] == "high"]
        if high_risks:
            # Send alert to supervisor
            self.send_to(
                recipient="supervisor",
                event="RISK_ESCALATION",
                data={
                    "summary": analysis.summary,
                    "risks": risks,
                    "recommendation": "immediate_review",
                },
            )
            return Decision(
                agent=self.name,
                action=DecisionAction.REDUCE,
                symbol="PORTFOLIO",
                confidence=0.9,
                reason=[r["recommendation"] for r in high_risks],
            )

        return Decision(
            agent=self.name,
            action=DecisionAction.HOLD,
            symbol="",
            confidence=0.7,
            reason=["Monitoring elevated risk levels"],
        )

    # ── Core Risk Assessment ────────────────────────────────────

    def evaluate_proposal(
        self,
        proposal_id: str,
        symbol: str,
        action: str,
        size_pct: float,
        confidence: float,
    ) -> RiskAssessment:
        """Evaluate a trade proposal against all risk policies.

        This is the core risk review function called for every trade.
        """
        checks = []
        violations = []
        warnings_list = []
        risk_score = 0.0

        # 1. Policy engine evaluation
        context = {
            "symbol": symbol,
            "action": action,
            "position_pct": size_pct,
            "confidence": confidence,
            "current_drawdown_pct": self._risk_metrics.get("current_drawdown_pct", 0),
            "daily_pnl_pct": self._risk_metrics.get("daily_pnl_pct", 0),
            "volatility": self._risk_metrics.get("volatility", 20),
            "leverage": self._risk_metrics.get("leverage", 1.0),
            "trades_this_hour": self._risk_metrics.get("trades_this_hour", 0),
            "top_holding_pct": self._risk_metrics.get("top_holding_pct", 0),
            "sector_exposure_pct": self._sector_exposures.get("technology", 0),
        }

        policy_result = self.policy_engine.evaluate(context)
        policy_action = policy_result.get("action", "allow")

        checks.append({
            "check": "policy_engine",
            "result": policy_action,
            "details": policy_result.get("reason", ""),
        })

        if policy_result.get("blocked"):
            risk_score = max(risk_score, 0.9)
            violations.extend(policy_result.get("rule_violations", []))

        # 2. Position size check
        current_position = self._position_sizes.get(symbol, 0)
        new_position = current_position + size_pct if action == "BUY" else current_position - size_pct

        if new_position > 10.0:
            checks.append({
                "check": "position_limit",
                "result": "violated",
                "current": current_position,
                "proposed": new_position,
                "limit": 10.0,
            })
            risk_score = max(risk_score, 0.7)
            violations.append({
                "rule_id": "POSITION_CHECK",
                "rule_type": "position_limit",
                "detail": f"Position would be {new_position:.1f}% (limit: 10%)",
            })
        elif new_position > 8.0:
            checks.append({
                "check": "position_warning",
                "result": "warning",
                "current": current_position,
                "proposed": new_position,
            })
            warnings_list.append(f"Position approaching limit: {new_position:.1f}%")
            risk_score = max(risk_score, 0.3)
        else:
            checks.append({
                "check": "position_limit",
                "result": "ok",
                "current": current_position,
                "proposed": new_position,
            })

        # 3. Confidence check
        if confidence < 0.5:
            checks.append({"check": "confidence", "result": "failed", "value": confidence, "threshold": 0.5})
            risk_score = max(risk_score, 0.8)
            violations.append({
                "rule_id": "CONFIDENCE_CHECK",
                "rule_type": "confidence",
                "detail": f"Confidence {confidence:.2f} below 0.5",
            })
        elif confidence < 0.6:
            checks.append({"check": "confidence", "result": "warning", "value": confidence, "threshold": 0.6})
            warnings_list.append(f"Low confidence: {confidence:.2f}")
            risk_score = max(risk_score, 0.4)
        else:
            checks.append({"check": "confidence", "result": "ok", "value": confidence})

        # 4. Market risk mode adjustment
        risk_mode = self.memory.get_working("risk_mode", "normal")
        if risk_mode == "conservative" and size_pct > 3.0:
            warnings_list.append(f"Conservative mode: reducing size from {size_pct:.1f}%")
            checks.append({"check": "risk_mode", "result": "size_reduced", "mode": risk_mode})
            risk_score = max(risk_score, 0.5)

        # 5. Liquidity check
        if size_pct > 5.0 and action == "SELL":
            checks.append({"check": "liquidity_sell", "result": "warning", "size": size_pct})
            warnings_list.append(f"Large sell order ({size_pct:.1f}%) may impact market")
            risk_score = max(risk_score, 0.3)

        # Determine final decision
        if risk_score >= 0.9 or any(
            v.get("rule_type") in ("daily_loss", "drawdown", "leverage")
            for v in violations
        ):
            decision = RiskDecision.BLOCKED
            approved_size = 0.0
        elif risk_score >= 0.7:
            decision = RiskDecision.REJECTED
            approved_size = 0.0
        elif risk_score >= 0.5:
            decision = RiskDecision.SIZE_REDUCED
            # Reduce size based on risk score
            reduction = 1.0 - risk_score
            approved_size = size_pct * max(0.25, reduction)
            checks.append({
                "check": "size_reduction",
                "original": size_pct,
                "approved": approved_size,
                "reason": f"Risk score {risk_score:.2f} triggered reduction",
            })
        elif warnings_list:
            decision = RiskDecision.APPROVED_WITH_WARNINGS
            approved_size = size_pct
        else:
            decision = RiskDecision.APPROVED
            approved_size = size_pct

        # Build reason
        reasons = []
        if violations:
            reasons.append(f"{len(violations)} violation(s)")
        if warnings_list:
            reasons.append(f"{len(warnings_list)} warning(s)")
        if not reasons:
            reasons.append("All checks passed")

        assessment = RiskAssessment(
            proposal_id=proposal_id,
            symbol=symbol,
            action=action,
            decision=decision,
            original_size=size_pct,
            approved_size=approved_size,
            confidence=confidence,
            risk_score=risk_score,
            checks=checks,
            violations=violations,
            warnings=warnings_list,
            reason="; ".join(reasons),
        )

        # Track statistics
        self._assessments.append(assessment)
        if assessment.decision in (RiskDecision.REJECTED, RiskDecision.BLOCKED):
            self._rejection_count += 1
            self._rejected_proposals.append({
                "proposal_id": proposal_id,
                "symbol": symbol,
                "reason": assessment.reason,
                "timestamp": time.time(),
            })
            if len(self._rejected_proposals) > 500:
                self._rejected_proposals = self._rejected_proposals[-500:]
        else:
            self._approval_count += 1

        self.memory.set_working("approvals", self._approval_count)
        self.memory.set_working("rejections", self._rejection_count)

        # Learn from this assessment
        self.memory.remember_episode(
            content=assessment.to_dict(),
            context={"proposal_id": proposal_id},
            tags=["risk_assessment", decision.value, symbol],
        )

        return assessment

    # ── Risk Metrics Management ─────────────────────────────────

    def update_risk_metrics(self, metrics: Dict[str, Any]) -> None:
        """Update current risk metrics."""
        self._risk_metrics.update(metrics)

    def update_sector_exposure(self, sector: str, exposure_pct: float) -> None:
        """Update sector exposure."""
        self._sector_exposures[sector] = exposure_pct

    def update_position(self, symbol: str, size_pct: float) -> None:
        """Update a position size."""
        self._position_sizes[symbol] = size_pct

    def get_rejection_reasons(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent rejection reasons for explainability."""
        return self._rejected_proposals[-limit:]

    # ── Query Methods ───────────────────────────────────────────

    def get_assessments(
        self, decision: RiskDecision = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get risk assessments with optional filter."""
        results = self._assessments
        if decision:
            results = [a for a in results if a.decision == decision]
        return [a.to_dict() for a in results[-limit:]]

    def get_risk_summary(self) -> Dict[str, Any]:
        """Get current risk summary."""
        return {
            "circuit_breaker": self.policy_engine.is_circuit_breaker_active(),
            "total_assessments": len(self._assessments),
            "approvals": self._approval_count,
            "rejections": self._rejection_count,
            "approval_rate": (
                self._approval_count / max(1, self._approval_count + self._rejection_count)
            ),
            "current_drawdown": self._risk_metrics.get("current_drawdown_pct", 0),
            "daily_pnl": self._risk_metrics.get("daily_pnl_pct", 0),
            "risk_mode": self.memory.get_working("risk_mode", "normal"),
            "policy_status": self.policy_engine.get_status(),
        }

    def get_status_report(self) -> Dict[str, Any]:
        report = super().get_status_report()
        report.update(self.get_risk_summary())
        return report
