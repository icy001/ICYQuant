"""
Automated Reporting — Automated risk report generation engine.

Generates formatted risk reports in JSON, PDF, and Excel formats
using report templates, with support for custom sections and metadata.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .report_templates import ReportTemplates

logger = logging.getLogger(__name__)


class AutomatedReporting:
    """
    Automated risk report generation engine.

    Generates standardized risk reports using predefined templates:
    - Daily Risk Report
    - Weekly Risk Report
    - Monthly Risk Report
    - Stress Test Report
    - Audit Report

    Output formats: JSON, PDF, Excel

    Usage::

        reporting = AutomatedReporting()
        await reporting.initialize()
        report = await reporting.generate_report(analytics_data, "daily")
    """

    def __init__(self, templates: Optional[ReportTemplates] = None) -> None:
        self._templates = templates or ReportTemplates()
        self._report_history: list[dict] = []
        self._max_history = 500
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the reporting engine."""
        self._initialized = True
        logger.info("AutomatedReporting initialized.")

    async def generate_report(
        self,
        data: dict[str, Any],
        report_type: str = "daily",
        format: str = "json",
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Generate a risk report.

        Parameters
        ----------
        data : dict
            Analytics results and portfolio data.
        report_type : str
            One of: daily, weekly, monthly, stress, audit.
        format : str
            Output format: json, pdf, excel.
        metadata : dict, optional
            Additional report metadata.

        Returns
        -------
        dict
            Report content (or metadata for binary formats).
        """
        if not self._initialized:
            await self.initialize()

        # Prepare data
        report_data = self._prepare_report_data(data)

        # Render template
        rendered = self._templates.render(report_type, report_data)
        if "error" in rendered:
            return rendered

        # Format output
        if format == "json":
            output = rendered
        elif format == "pdf":
            output = await self._generate_pdf(rendered, report_type)
        elif format == "excel":
            output = await self._generate_excel(rendered, report_type)
        else:
            output = rendered

        # Add metadata
        report = {
            "report_id": self._generate_report_id(report_type),
            "report_type": report_type,
            "format": format,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
            "content": output,
        }

        # Store in history
        self._report_history.append(report)
        if len(self._report_history) > self._max_history:
            self._report_history = self._report_history[-self._max_history:]

        logger.info(f"AutomatedReporting: generated {report_type} report in {format}.")
        return report

    async def generate_batch(
        self,
        data: dict[str, Any],
        report_types: list[str],
        format: str = "json",
    ) -> dict[str, Any]:
        """Generate multiple report types in parallel."""
        tasks = [
            asyncio.create_task(self.generate_report(data, rt, format))
            for rt in report_types
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        reports = {}
        for rt, res in zip(report_types, results):
            if isinstance(res, Exception):
                reports[rt] = {"error": str(res)}
            else:
                reports[rt] = res

        return {
            "batch_size": len(report_types),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "reports": reports,
        }

    async def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get report generation history."""
        return [
            {
                "report_id": r.get("report_id"),
                "report_type": r.get("report_type"),
                "format": r.get("format"),
                "generated_at": r.get("generated_at"),
            }
            for r in self._report_history[-limit:]
        ]

    # ---- Internal ----

    def _prepare_report_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Prepare and normalize data for report rendering."""
        prepared: dict[str, Any] = {}

        # Dashboard data
        dashboard = data.get("dashboard", {}) or data
        prepared.update({
            "portfolio_value": data.get("portfolio_value", dashboard.get("portfolio_value", 0)),
            "daily_pnl": data.get("daily_pnl", 0),
            "daily_pnl_pct": data.get("daily_pnl_pct", 0),
            "mtd_pnl": data.get("mtd_pnl", 0),
            "ytd_pnl": data.get("ytd_pnl", 0),
            "var_95_1d": data.get("var_95_1d", 0),
            "var_99_1d": data.get("var_99_1d", 0),
            "cvar_95": data.get("cvar_95", 0),
            "overall_status": data.get("overall_status", "unknown"),
        })

        # Stress data
        stress = data.get("stress_testing", {})
        prepared.update({
            "total_scenarios": stress.get("total_scenarios", 0),
            "stress_passed": stress.get("passed", 0),
            "stress_failed": stress.get("failed", 0),
            "worst_stress_scenario": stress.get("worst_case_scenario", ""),
            "worst_stress_loss_pct": stress.get("worst_case_loss_pct", 0),
        })

        # Capital data
        capital = data.get("capital_adequacy", {})
        prepared.update({
            "capital_ratio": capital.get("ratios", {}).get("car_pct", 0),
            "capital_surplus": capital.get("capital_surplus", 0),
            "regulatory_status": capital.get("regulatory_status", "unknown"),
        })

        # Alerts
        prepared.update({
            "active_alerts": data.get("active_alerts", 0),
            "critical_alerts": data.get("critical_alerts", 0),
        })

        # Drawdown
        prepared.update({
            "current_drawdown_pct": data.get("current_drawdown_pct", 0),
            "max_drawdown_pct": data.get("max_drawdown_pct", 0),
        })

        # Attribution
        prepared["attribution"] = data.get("attribution", {})

        # Factor decomposition
        prepared["factor_decomposition"] = data.get("factor_decomposition", {})

        # Recommendations
        scenario_comparison = data.get("scenario_comparison", {})
        prepared["recommendations"] = (
            data.get("recommendations", [])
            or scenario_comparison.get("recommendations", [])
        )

        return prepared

    def _generate_report_id(self, report_type: str) -> str:
        """Generate a unique report ID."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"rpt-{report_type}-{ts}"

    async def _generate_pdf(self, rendered: dict, report_type: str) -> dict:
        """Generate PDF report (placeholder)."""
        return {
            "format": "pdf",
            "report_type": report_type,
            "status": "placeholder",
            "note": "PDF generation requires additional dependency (e.g., weasyprint, reportlab).",
            "rendered_sections": list(rendered.get("sections", {}).keys()),
        }

    async def _generate_excel(self, rendered: dict, report_type: str) -> dict:
        """Generate Excel report (placeholder)."""
        return {
            "format": "excel",
            "report_type": report_type,
            "status": "placeholder",
            "note": "Excel generation requires additional dependency (e.g., openpyxl).",
            "rendered_sections": list(rendered.get("sections", {}).keys()),
        }
