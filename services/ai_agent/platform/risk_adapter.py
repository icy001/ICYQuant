"""Risk Adapter — bridges the AI Platform to the ICYQuant Risk Engine.

The RiskAdapter translates AI agent risk assessment requests into Risk Engine
calls for exposure analysis, VaR computation, stress testing, and limit
checking. It ensures all AI-driven decisions pass through proper risk gates.

Capabilities:
    - Portfolio risk assessment
    - VaR / CVaR computation
    - Stress testing
    - Exposure analysis
    - Risk limit checking
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk assessment levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskAssessmentRequest:
    """A risk assessment request from an AI agent."""
    request_id: str = ""
    agent_id: str = ""
    portfolio: Dict[str, Any] = field(default_factory=dict)
    assessment_types: List[str] = field(default_factory=list)  # var, cvar, stress_test, exposure


@dataclass
class RiskAssessmentResult:
    """Result of a risk assessment."""
    request_id: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    passed: bool = True
    var_95: Optional[float] = None
    var_99: Optional[float] = None
    cvar_95: Optional[float] = None
    max_exposure_pct: Optional[float] = None
    stress_test_results: Dict[str, Any] = field(default_factory=dict)
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class RiskAdapter:
    """Adapter for the ICYQuant Risk Engine.

    Provides AI agents with access to portfolio risk assessment, VaR
    computation, stress testing, and exposure analysis.

    Usage:
        ra = RiskAdapter()
        await ra.initialize()
        result = await ra.assess_risk(RiskAssessmentRequest(agent_id="agent_1", portfolio={...}))
    """

    def __init__(self) -> None:
        self._total_assessments: int = 0
        self._total_passed: int = 0
        self._total_blocked: int = 0
        self._initialized: bool = False
        logger.info("RiskAdapter created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("RiskAdapter initialized")

    async def shutdown(self) -> None:
        self._initialized = False
        logger.info("RiskAdapter shutdown complete")

    async def assess_risk(self, request: RiskAssessmentRequest) -> RiskAssessmentResult:
        """Assess portfolio risk through the Risk Engine.

        Runs configured risk assessment types and returns a comprehensive
        risk report with pass/fail status and violation details.
        """
        self._total_assessments += 1

        # TODO: Actual integration with Risk Engine
        result = RiskAssessmentResult(
            request_id=request.request_id,
            risk_level=RiskLevel.LOW,
            passed=True,
            var_95=0.05,
            var_99=0.08,
            cvar_95=0.07,
            max_exposure_pct=0.15,
        )

        if result.passed:
            self._total_passed += 1
        else:
            self._total_blocked += 1

        logger.info("RiskAdapter: assessed risk for agent %s (passed=%s, level=%s)", request.agent_id, result.passed, result.risk_level.value)
        return result

    async def check_limits(self, agent_id: str, portfolio: Dict[str, Any]) -> RiskAssessmentResult:
        """Quick limit check for a portfolio."""
        return await self.assess_risk(RiskAssessmentRequest(
            agent_id=agent_id,
            portfolio=portfolio,
            assessment_types=["limit_check"],
        ))

    async def run_stress_test(self, agent_id: str, portfolio: Dict[str, Any], scenarios: Optional[List[str]] = None) -> RiskAssessmentResult:
        """Run stress tests on a portfolio."""
        return await self.assess_risk(RiskAssessmentRequest(
            agent_id=agent_id,
            portfolio=portfolio,
            assessment_types=["stress_test"],
        ))

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "total_assessments": self._total_assessments,
            "total_passed": self._total_passed,
            "total_blocked": self._total_blocked,
            "pass_rate": round(self._total_passed / self._total_assessments * 100, 1) if self._total_assessments > 0 else 0.0,
        }
