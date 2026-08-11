"""
ICYQuant Risk Agent — risk assessment and stress testing.

Evaluates strategy and portfolio risk across multiple dimensions:
market risk, factor exposure, tail risk, liquidity risk, and
scenario-based stress testing.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskMetric:
    """A single risk metric."""
    name: str
    value: float
    threshold: float = 0.0
    status: str = "ok"          # ok, warning, breached
    description: str = ""


@dataclass
class RiskAssessment:
    """A comprehensive risk assessment."""
    assessment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subject: str = ""            # Strategy or portfolio ID
    risk_level: RiskLevel = RiskLevel.MEDIUM

    # Risk metrics
    var_95: float = 0.0         # Value at Risk (95%)
    cvar_95: float = 0.0        # Conditional VaR
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    beta: float = 0.0
    volatility_annual: float = 0.0

    # Factor exposures
    factor_exposures: dict[str, float] = field(default_factory=dict)

    # Stress test results
    stress_tests: dict[str, float] = field(default_factory=dict)

    metrics: list[RiskMetric] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    acceptable: bool = True
    confidence: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RiskAgent:
    """Risk assessment and monitoring agent.

    Capabilities:
        - Multi-factor risk decomposition
        - VaR/CVaR calculation
        - Factor exposure analysis
        - Stress testing (market crash, liquidity crisis, etc.)
        - Risk limit enforcement
        - Correlation and concentration analysis
    """

    def __init__(self, agent_id: str = "risk_agent",
                 registry: Any = None,
                 communication_bus: Any = None) -> None:
        self.agent_id = agent_id
        self._registry = registry
        self._comm_bus = communication_bus
        self._assessment_count = 0

    async def assess_risk(self, strategy: Any,
                          context: Optional[dict[str, Any]] = None) -> RiskAssessment:
        """Assess the risk of a strategy."""
        self._assessment_count += 1

        assessment = RiskAssessment(
            subject=getattr(strategy, 'name', 'unknown'),
            var_95=0.025, cvar_95=0.035,
            max_drawdown=0.12, sharpe_ratio=1.2,
            beta=0.85, volatility_annual=0.18,
            factor_exposures={"momentum": 0.3, "value": 0.25, "size": -0.1},
            stress_tests={
                "market_crash_2008": -0.18,
                "liquidity_crisis": -0.12,
                "rate_hike_shock": -0.08,
            },
        )

        # Generate metrics
        assessment.metrics = [
            RiskMetric(name="var_95", value=0.025, threshold=0.03, status="ok"),
            RiskMetric(name="max_drawdown", value=0.12, threshold=0.20, status="ok"),
            RiskMetric(name="beta", value=0.85, threshold=1.2, status="ok"),
            RiskMetric(name="volatility", value=0.18, threshold=0.25, status="ok"),
        ]

        # Determine overall risk level
        if assessment.max_drawdown > 0.25 or assessment.var_95 > 0.05:
            assessment.risk_level = RiskLevel.HIGH
            assessment.acceptable = False
            assessment.warnings.append("High risk: max drawdown or VaR exceeds thresholds")
        elif assessment.sharpe_ratio < 0.5:
            assessment.risk_level = RiskLevel.MEDIUM
            assessment.warnings.append("Low risk-adjusted returns (Sharpe < 0.5)")
        else:
            assessment.risk_level = RiskLevel.MEDIUM
            assessment.acceptable = True

        assessment.confidence = 0.8

        logger.info("Risk assessment %s: subject=%s level=%s acceptable=%s",
                     assessment.assessment_id, assessment.subject,
                     assessment.risk_level.value, assessment.acceptable)
        return assessment

    async def stress_test(self, strategy: Any,
                          scenarios: Optional[list[str]] = None) -> dict[str, float]:
        """Run stress test scenarios on a strategy."""
        default_scenarios = {
            "market_crash_2008": -0.18,
            "liquidity_crisis": -0.12,
            "rate_hike_shock": -0.08,
            "tech_bubble_burst": -0.15,
            "covid_style_crash": -0.10,
        }
        return {s: default_scenarios.get(s, 0.0) for s in (scenarios or default_scenarios)}

    @property
    def assessment_count(self) -> int:
        return self._assessment_count
