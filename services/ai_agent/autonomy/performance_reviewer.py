"""Performance Reviewer — autonomously analyzes execution results vs expectations.

Pipeline:
    Execution Result -> PerformanceReviewer.review()
        -> Compare expected vs actual returns
        -> Attribution analysis (factor, sector, timing)
        -> Deviation analysis
        -> Generate PerformanceReport
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PerformanceReport:
    """Performance review report.

    Attributes:
        report_id: Unique identifier.
        workflow_id: Parent workflow.
        expected_return: Predicted return.
        actual_return: Realized return.
        deviation: Return deviation.
        attribution: Attribution breakdown.
        insights: Generated insights.
        recommendations: Improvement recommendations.
        reviewed_at: Review timestamp.
    """

    report_id: str = ""
    workflow_id: str = ""
    expected_return: float = 0.0
    actual_return: float = 0.0
    deviation: float = 0.0
    attribution: Dict[str, float] = field(default_factory=dict)
    insights: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    reviewed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_outperforming(self) -> bool:
        return self.actual_return > self.expected_return

    @property
    def deviation_bps(self) -> float:
        return self.deviation * 10000


class PerformanceReviewer:
    """Analyzes execution results against expectations.

    Compares expected vs actual performance, performs attribution
    analysis, and generates actionable insights for the feedback loop.

    Supports:
        - Expected vs actual comparison
        - Factor/sector/timing attribution
        - Deviation analysis
        - Insight and recommendation generation

    Usage:
        reviewer = PerformanceReviewer()
        await reviewer.initialize()
        report = await reviewer.review(workflow, expected_return=0.05, actual_return=0.04)
    """

    def __init__(self) -> None:
        self._reports: List[PerformanceReport] = []
        self._counter: int = 0
        self._initialized: bool = False
        logger.info("PerformanceReviewer created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("PerformanceReviewer initialized")

    async def shutdown(self) -> None:
        self._reports.clear()
        self._initialized = False
        logger.info("PerformanceReviewer shutdown complete")

    async def review(
        self,
        workflow: Optional[Any] = None,
        expected_return: float = 0.0,
        actual_return: float = 0.0,
        attribution: Optional[Dict[str, float]] = None,
    ) -> PerformanceReport:
        """Generate a performance review.

        Args:
            workflow: The workflow context.
            expected_return: Predicted return.
            actual_return: Realized return.
            attribution: Attribution breakdown.

        Returns:
            PerformanceReport with analysis.
        """
        self._counter += 1
        wf_id = getattr(workflow, "workflow_id", "") if workflow else ""
        report = PerformanceReport(
            report_id=f"perf_{self._counter}",
            workflow_id=wf_id,
            expected_return=expected_return,
            actual_return=actual_return,
            deviation=actual_return - expected_return,
            attribution=attribution or {},
        )

        if report.is_outperforming:
            report.insights.append(f"Outperformed by {report.deviation_bps:.1f} bps")
        else:
            report.insights.append(f"Underperformed by {abs(report.deviation_bps):.1f} bps")
            report.recommendations.append("Review signal quality and factor selection")

        self._reports.append(report)
        logger.info("PerformanceReviewer.review() completed: deviation=%.1f bps", report.deviation_bps)
        return report

    def get_recent_reports(self, limit: int = 10) -> List[Dict[str, Any]]:
        return [
            {
                "id": r.report_id,
                "workflow_id": r.workflow_id,
                "expected": round(r.expected_return, 4),
                "actual": round(r.actual_return, 4),
                "deviation_bps": round(r.deviation_bps, 1),
                "outperforming": r.is_outperforming,
            }
            for r in self._reports[-limit:]
        ]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "total_reports": len(self._reports),
        }
