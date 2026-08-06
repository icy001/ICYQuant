"""Report Center — unified report generation and distribution hub.

Commit 11 Part 1.5: Central report generation for all research outputs
including factor reports, backtest reports, portfolio reports, and
research summaries.

Output formats:
    - HTML (interactive dashboards)
    - JSON (API consumption)
    - PDF (reserved)
    - Markdown (reserved)

Architecture::

    Factor Report + Backtest Report + Portfolio Report + Research Summary
    → Report Center → HTML / JSON / PDF / MD
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ReportCenterState(str, Enum):
    """Report center lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    ERROR = "error"


class ReportType(str, Enum):
    """Supported report types."""

    FACTOR = "factor"
    BACKTEST = "backtest"
    PORTFOLIO = "portfolio"
    RESEARCH_SUMMARY = "research_summary"
    CUSTOM = "custom"


class ReportFormat(str, Enum):
    """Report output formats."""

    HTML = "html"
    JSON = "json"
    PDF = "pdf"
    MARKDOWN = "markdown"


class ReportCenter:
    """Central report generation and distribution hub.

    Aggregates research outputs from all subsystems and generates
    unified reports in multiple formats.

    Usage::

        center = ReportCenter(config={"output_dir": "/reports"})
        await center.initialize()
        report = await center.generate_report(
            report_type=ReportType.BACKTEST,
            data={"backtest_id": "bt-123", "metrics": {...}},
        )
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        center_id: Optional[str] = None,
    ) -> None:
        self._id: str = center_id or f"rpt-{uuid4().hex[:12]}"
        self._config: Dict[str, Any] = config or {}
        self._state: ReportCenterState = ReportCenterState.UNINITIALIZED
        self._created_at: datetime = datetime.now(timezone.utc)

        # Configuration
        self._output_dir: str = self._config.get("output_dir", "./reports")
        self._default_format: ReportFormat = ReportFormat(self._config.get("default_format", "html"))

        # Report store
        self._reports: Dict[str, Dict[str, Any]] = {}
        self._templates: Dict[ReportType, str] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self._id

    @property
    def state(self) -> ReportCenterState:
        return self._state

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize report center."""
        self._state = ReportCenterState.INITIALIZING
        logger.info("Initializing ReportCenter [%s] output_dir=%s", self._id, self._output_dir)

        # Register default templates
        self._templates = {
            ReportType.FACTOR: "factor_report_template",
            ReportType.BACKTEST: "backtest_report_template",
            ReportType.PORTFOLIO: "portfolio_report_template",
            ReportType.RESEARCH_SUMMARY: "research_summary_template",
            ReportType.CUSTOM: "custom_report_template",
        }

        self._state = ReportCenterState.READY
        logger.info("ReportCenter initialized [%s]", self._id)

    async def shutdown(self) -> None:
        """Clean up."""
        self._reports.clear()
        self._state = ReportCenterState.UNINITIALIZED

    # ------------------------------------------------------------------
    # Report Generation
    # ------------------------------------------------------------------

    async def generate_report(
        self,
        report_type: ReportType,
        data: Dict[str, Any],
        *,
        title: Optional[str] = None,
        format: Optional[ReportFormat] = None,
        template: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a research report.

        Args:
            report_type: Type of report.
            data: Report data/context.
            title: Report title.
            format: Output format (default: HTML).
            template: Custom template name.

        Returns:
            Report metadata with access URL.
        """
        report_id = f"rpt-{uuid4().hex[:12]}"
        fmt = format or self._default_format

        logger.info("Generating %s report [%s] format=%s", report_type.value, report_id, fmt.value)

        # Simulate report generation
        await asyncio.sleep(0.01)

        report = {
            "id": report_id,
            "type": report_type.value,
            "title": title or f"{report_type.value.title()} Report",
            "format": fmt.value,
            "template": template or self._templates.get(report_type, "default"),
            "data_summary": {
                "sections": self._get_sections(report_type),
                "data_keys": list(data.keys()) if data else [],
            },
            "url": f"/reports/{report_type.value}/{report_id}.{fmt.value}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._reports[report_id] = report
        logger.info("Report generated: %s [%s]", report_id, report_type.value)
        return dict(report)

    def _get_sections(self, report_type: ReportType) -> List[str]:
        """Get default report sections per type."""
        sections = {
            ReportType.FACTOR: [
                "Factor Summary", "IC Analysis", "Factor Distribution",
                "Sector Exposure", "Turnover Analysis", "Performance Attribution",
            ],
            ReportType.BACKTEST: [
                "Executive Summary", "Strategy Overview", "Performance Metrics",
                "Risk Analysis", "Equity Curve", "Trade Analysis", "Drawdown Analysis",
            ],
            ReportType.PORTFOLIO: [
                "Portfolio Summary", "Optimization Results", "Risk Analysis",
                "Exposure Analysis", "Stress Test Results", "Attribution Analysis",
            ],
            ReportType.RESEARCH_SUMMARY: [
                "Platform Overview", "Active Experiments", "Factor Performance",
                "Backtest Results", "Portfolio Status", "Model Registry",
            ],
            ReportType.CUSTOM: ["Custom Report"],
        }
        return sections.get(report_type, ["Report"])

    # ------------------------------------------------------------------
    # Batch Generation
    # ------------------------------------------------------------------

    async def generate_batch(
        self,
        reports: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Generate multiple reports in batch.

        Args:
            reports: List of {"type": ReportType, "data": {...}, "title": "..."}.

        Returns:
            List of generated report metadata.
        """
        results = []
        for req in reports:
            result = await self.generate_report(
                report_type=req.get("type", ReportType.CUSTOM),
                data=req.get("data", {}),
                title=req.get("title"),
                format=req.get("format"),
            )
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Report Retrieval
    # ------------------------------------------------------------------

    async def get_report(self, report_id: str) -> Dict[str, Any]:
        """Get report details."""
        report = self._reports.get(report_id)
        if report is None:
            raise KeyError(f"Report not found: {report_id}")
        return dict(report)

    async def list_reports(
        self,
        report_type: Optional[ReportType] = None,
    ) -> List[Dict[str, Any]]:
        """List generated reports."""
        reports = list(self._reports.values())
        if report_type is not None:
            reports = [r for r in reports if r["type"] == report_type.value]
        return [
            {"id": r["id"], "type": r["type"], "title": r["title"], "format": r["format"], "url": r["url"]}
            for r in reports
        ]

    async def delete_report(self, report_id: str) -> None:
        """Delete a report."""
        if report_id not in self._reports:
            raise KeyError(f"Report not found: {report_id}")
        del self._reports[report_id]
        logger.info("Report deleted: %s", report_id)
