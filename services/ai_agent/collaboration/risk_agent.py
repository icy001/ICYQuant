"""Risk Agent — specialized agent for risk assessment, limit checking, and stress testing.

Pipeline:
    Risk assessment request / Coordinator assignment
        -> RiskAgent.assess() (compute risk metrics)
        -> RiskAgent.check_limits() (verify against limits)
        -> RiskAgent.stress_test() (scenario analysis)
        -> RiskAgent.issue_alert() (if risk threshold breached)
        -> publish risk report to blackboard

The Risk Agent has veto power over trading decisions through the
Conflict Resolver's safety-first policy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.ai_agent.collaboration.message_bus import MessageBus, Message, MessageType

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskAlertType(str, Enum):
    """Types of risk alerts."""
    LIMIT_BREACH = "limit_breach"
    VAR_EXCEEDED = "var_exceeded"
    CONCENTRATION = "concentration"
    LIQUIDITY = "liquidity"
    VOLATILITY_SPIKE = "volatility_spike"
    DRAWDOWN = "drawdown"


@dataclass
class RiskAssessment:
    """Result of a risk assessment.

    Attributes:
        assessment_id: Unique assessment identifier.
        overall_level: Overall risk level.
        metrics: Detailed risk metrics.
        alerts: Active risk alerts.
        limits_breached: Limits that were breached.
        recommendations: Risk mitigation recommendations.
        timestamp: Assessment timestamp.
    """

    assessment_id: str = field(default_factory=lambda: uuid4().hex)
    overall_level: RiskLevel = RiskLevel.LOW
    metrics: Dict[str, Any] = field(default_factory=dict)
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    limits_breached: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RiskAgent:
    """Specialized agent for risk assessment and management.

    Computes risk metrics, checks against configured limits, performs
    stress testing, and issues alerts. Has veto power over trading
    decisions through the safety-first conflict resolution policy.

    Supports:
        - Risk metric computation (VaR, ES, drawdown, etc.)
        - Limit checking and breach detection
        - Stress testing and scenario analysis
        - Risk alert generation
        - Risk mitigation recommendations

    Usage:
        agent = RiskAgent(agent_id="risk_1", message_bus=bus)
        await agent.initialize()
        assessment = await agent.assess(portfolio_data)
        if assessment.overall_level == RiskLevel.CRITICAL:
            await agent.issue_alert(assessment)
    """

    def __init__(
        self,
        agent_id: str = "",
        message_bus: Optional[MessageBus] = None,
    ) -> None:
        """Initialize the Risk Agent.

        Args:
            agent_id: Unique agent identifier.
            message_bus: Message bus for communication.
        """
        self._agent_id: str = agent_id or uuid4().hex[:12]
        self._message_bus: Optional[MessageBus] = message_bus
        self._initialized: bool = False
        self._assessments: List[RiskAssessment] = []
        self._risk_limits: Dict[str, float] = {
            "max_var_pct": 0.05,
            "max_drawdown": 0.20,
            "max_concentration": 0.25,
            "max_leverage": 2.0,
        }
        logger.info("RiskAgent created: %s", self._agent_id)

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the risk agent."""
        if self._initialized:
            return
        self._initialized = True
        logger.info("RiskAgent initialized: %s", self._agent_id)

    async def shutdown(self) -> None:
        """Shut down the risk agent."""
        self._assessments.clear()
        self._initialized = False
        logger.info("RiskAgent shutdown: %s", self._agent_id)

    # ── Assessment ──

    async def assess(
        self, portfolio_data: Dict[str, Any],
    ) -> RiskAssessment:
        """Perform a comprehensive risk assessment.

        Args:
            portfolio_data: Portfolio and market data for assessment.

        Returns:
            RiskAssessment with metrics and alerts.
        """
        assessment = RiskAssessment()

        # Compute risk metrics
        total_value = portfolio_data.get("total_value", 0.0)
        var_95 = total_value * 0.02
        expected_shortfall = total_value * 0.025
        max_drawdown = portfolio_data.get("max_drawdown", -0.15)
        concentration = portfolio_data.get("concentration", 0.0)

        assessment.metrics = {
            "var_95": var_95,
            "var_95_pct": 0.02,
            "expected_shortfall": expected_shortfall,
            "max_drawdown": max_drawdown,
            "concentration": concentration,
            "volatility": portfolio_data.get("volatility", 0.15),
            "leverage": portfolio_data.get("leverage", 1.0),
        }

        # Check limits
        limits_breached: List[str] = []
        alerts: List[Dict[str, Any]] = []

        if assessment.metrics["var_95_pct"] > self._risk_limits["max_var_pct"]:
            limits_breached.append("var_limit")
            alerts.append({
                "type": RiskAlertType.VAR_EXCEEDED.value,
                "message": f"VaR ({assessment.metrics['var_95_pct']:.1%}) exceeds limit "
                          f"({self._risk_limits['max_var_pct']:.1%})",
                "severity": RiskLevel.HIGH.value,
            })

        if abs(max_drawdown) > self._risk_limits["max_drawdown"]:
            limits_breached.append("drawdown_limit")
            alerts.append({
                "type": RiskAlertType.DRAWDOWN.value,
                "message": f"Drawdown ({max_drawdown:.1%}) exceeds limit "
                          f"({self._risk_limits['max_drawdown']:.1%})",
                "severity": RiskLevel.CRITICAL.value,
            })

        if concentration > self._risk_limits["max_concentration"]:
            limits_breached.append("concentration_limit")
            alerts.append({
                "type": RiskAlertType.CONCENTRATION.value,
                "message": f"Concentration ({concentration:.1%}) exceeds limit "
                          f"({self._risk_limits['max_concentration']:.1%})",
                "severity": RiskLevel.HIGH.value,
            })

        assessment.limits_breached = limits_breached
        assessment.alerts = alerts

        # Determine overall risk level
        if any(a["severity"] == RiskLevel.CRITICAL.value for a in alerts):
            assessment.overall_level = RiskLevel.CRITICAL
        elif len(alerts) >= 2:
            assessment.overall_level = RiskLevel.HIGH
        elif len(alerts) == 1:
            assessment.overall_level = RiskLevel.MEDIUM
        else:
            assessment.overall_level = RiskLevel.LOW

        # Recommendations
        if limits_breached:
            assessment.recommendations = [
                "Reduce position sizes to stay within VaR limits",
                "Review portfolio concentration",
                "Consider hedging strategies",
            ]

        self._assessments.append(assessment)

        if self._message_bus:
            await self._message_bus.publish(Message(
                msg_type=MessageType.PUBLISH,
                topic="risk.assessment",
                sender_id=self._agent_id,
                payload={
                    "assessment_id": assessment.assessment_id,
                    "overall_level": assessment.overall_level.value,
                    "alerts": assessment.alerts,
                    "limits_breached": limits_breached,
                },
            ))

        logger.info("RiskAgent assessed: level=%s, alerts=%d",
                    assessment.overall_level.value, len(alerts))
        return assessment

    # ── Limit Checking ──

    async def check_limits(self, order: Dict[str, Any]) -> bool:
        """Check whether an order violates risk limits.

        Args:
            order: Order parameters.

        Returns:
            True if the order passes risk checks, False if blocked.
        """
        order_value = order.get("value", 0.0)
        symbol = order.get("symbol", "unknown")

        # Simulate risk checks
        if order_value > 1_000_000:
            logger.warning("RiskAgent blocked order: %s value too large (%.2f)",
                          symbol, order_value)
            return False

        logger.debug("RiskAgent approved order: %s (value=%.2f)", symbol, order_value)
        return True

    # ── Stress Testing ──

    async def stress_test(
        self, scenarios: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Run stress test scenarios.

        Args:
            scenarios: List of stress scenarios. Uses defaults if not provided.

        Returns:
            Stress test results per scenario.
        """
        default_scenarios = scenarios or [
            {"name": "market_crash", "shock": -0.30},
            {"name": "volatility_spike", "shock": 0.50},
            {"name": "liquidity_crisis", "shock": -0.15},
            {"name": "interest_rate_hike", "shock": -0.10},
        ]

        results: Dict[str, Any] = {"scenarios": {}}
        for scenario in default_scenarios:
            results["scenarios"][scenario["name"]] = {
                "pnl_impact": scenario["shock"],
                "var_impact": scenario["shock"] * 1.5,
                "passes": abs(scenario["shock"]) < 0.20,
            }

        logger.info("RiskAgent stress tested %d scenarios", len(default_scenarios))
        return results

    # ── Alerts ──

    async def issue_alert(self, assessment: RiskAssessment) -> None:
        """Issue a risk alert to all agents.

        Args:
            assessment: The risk assessment with alerts.
        """
        if self._message_bus:
            await self._message_bus.publish(Message(
                msg_type=MessageType.BROADCAST,
                topic="risk.alert",
                sender_id=self._agent_id,
                payload={
                    "level": assessment.overall_level.value,
                    "alerts": assessment.alerts,
                    "recommendations": assessment.recommendations,
                },
            ))
        logger.warning("RiskAgent issued alert: level=%s", assessment.overall_level.value)

    # ── Properties ──

    @property
    def agent_id(self) -> str:
        """Return the agent ID."""
        return self._agent_id

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the risk agent state.

        Returns:
            Dict with assessment count and limits.
        """
        return {
            "agent_id": self._agent_id,
            "initialized": self._initialized,
            "total_assessments": len(self._assessments),
            "risk_limits": self._risk_limits,
        }
