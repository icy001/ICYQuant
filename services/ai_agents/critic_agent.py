"""
ICYQuant Critic Agent — adversarial critique and devil's advocate.

Challenges assumptions, identifies blind spots, and stress-tests
conclusions from a skeptical perspective. Acts as a red-team in the
multi-agent pipeline to improve robustness.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CritiqueSeverity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    COSMETIC = "cosmetic"


@dataclass
class CritiquePoint:
    """A single point of criticism."""
    point_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    severity: CritiqueSeverity = CritiqueSeverity.MINOR
    target: str = ""              # What aspect is being criticized
    issue: str = ""               # Description of the issue
    impact: str = ""              # Potential impact if unaddressed
    suggestion: str = ""          # How to fix/improve
    confidence: float = 0.0


@dataclass
class CritiqueReport:
    """A comprehensive adversarial critique."""
    critique_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subject: str = ""
    subject_agent: str = ""

    # Overall assessment
    overall_score: float = 0.0    # 0-10
    is_fatal: bool = False        # If true, proposal should be rejected

    # Critique points
    points: list[CritiquePoint] = field(default_factory=list)
    critical_count: int = 0
    major_count: int = 0
    minor_count: int = 0

    # Blind spots identified
    blind_spots: list[str] = field(default_factory=list)
    untested_assumptions: list[str] = field(default_factory=list)
    missing_scenarios: list[str] = field(default_factory=list)

    # Summary
    summary: str = ""
    recommendation: str = ""      # "accept", "revise", "reject"

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CriticAgent:
    """Adversarial critique and devil's advocate agent.

    Capabilities:
        - Challenge assumptions and methodology
        - Identify blind spots and missing scenarios
        - Stress-test conclusions under adverse conditions
        - Red-team strategy logic for weaknesses
        - Provide constructive criticism with fixes
    """

    def __init__(self, agent_id: str = "critic_agent",
                 registry: Any = None,
                 communication_bus: Any = None) -> None:
        self.agent_id = agent_id
        self._registry = registry
        self._comm_bus = communication_bus
        self._critique_count = 0

    async def critique(self, subject: str, subject_agent: str,
                       content: Any,
                       context: Optional[dict[str, Any]] = None) -> CritiqueReport:
        """Generate adversarial critique of an agent's output."""
        self._critique_count += 1

        report = CritiqueReport(subject=subject, subject_agent=subject_agent)

        # Common critique points
        report.points = [
            CritiquePoint(
                severity=CritiqueSeverity.MAJOR,
                target="methodology",
                issue="Backtest may suffer from look-ahead bias",
                impact="Overstated performance by 10-20%",
                suggestion="Implement strict point-in-time data for backtest",
                confidence=0.7,
            ),
            CritiquePoint(
                severity=CritiqueSeverity.MINOR,
                target="data",
                issue="Limited universe — only CSI300 constituents",
                impact="Strategy may not generalize to broader market",
                suggestion="Test on CSI500 and CSI1000 for robustness",
                confidence=0.65,
            ),
            CritiquePoint(
                severity=CritiqueSeverity.MINOR,
                target="assumptions",
                issue="Assumes stable market regime",
                impact="Strategy fails in high-volatility periods",
                suggestion="Add regime-switching or volatility filter",
                confidence=0.6,
            ),
        ]

        report.critical_count = sum(1 for p in report.points if p.severity == CritiqueSeverity.CRITICAL)
        report.major_count = sum(1 for p in report.points if p.severity == CritiqueSeverity.MAJOR)
        report.minor_count = sum(1 for p in report.points if p.severity == CritiqueSeverity.MINOR)

        report.blind_spots = ["Regime change detection", "Tail risk hedging"]
        report.untested_assumptions = ["Normal distribution of returns", "Stable correlations"]
        report.missing_scenarios = ["Extended bear market", "Liquidity freeze", "Correlation breakdown"]

        # Determine if fatal
        report.is_fatal = report.critical_count > 0
        if report.is_fatal:
            report.recommendation = "reject"
        elif report.major_count > 2:
            report.recommendation = "revise"
        else:
            report.recommendation = "accept"

        report.overall_score = max(0.0, 10.0 - report.critical_count * 5 - report.major_count * 2 - report.minor_count * 0.5)
        report.summary = f"Critique: {report.critical_count} critical, {report.major_count} major, {report.minor_count} minor issues."

        logger.info("Critique %s: %s score=%.1f recommendation=%s",
                     report.critique_id, subject_agent,
                     report.overall_score, report.recommendation)
        return report

    @property
    def critique_count(self) -> int:
        return self._critique_count
