"""
Report Templates — Standardized templates for automated risk reports.

Provides pre-built templates for daily, weekly, monthly, stress,
and audit reports with configurable sections and formatting.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ReportTemplates:
    """
    Standardized report templates for risk reporting.

    Templates:
    - Daily Risk Report
    - Weekly Risk Report
    - Monthly Risk Report
    - Stress Test Report
    - Audit Report
    - Custom Report

    Usage::

        templates = ReportTemplates()
        template = templates.get("daily")
        report = templates.render("daily", data)
    """

    TEMPLATES = {
        "daily": {
            "title": "Daily Risk Report",
            "sections": [
                "executive_summary",
                "pnl_summary",
                "var_cvar",
                "exposure",
                "alerts",
                "drawdown",
            ],
            "format": "pdf",
        },
        "weekly": {
            "title": "Weekly Risk Report",
            "sections": [
                "executive_summary",
                "pnl_weekly",
                "var_cvar",
                "exposure_trend",
                "stress_tests",
                "attribution",
                "alerts_summary",
                "recommendations",
            ],
            "format": "pdf",
        },
        "monthly": {
            "title": "Monthly Risk Report",
            "sections": [
                "executive_summary",
                "pnl_monthly",
                "var_cvar_monthly",
                "stress_tests",
                "attribution",
                "factor_decomposition",
                "capital_adequacy",
                "concentration",
                "scenario_comparison",
                "recommendations",
                "appendix",
            ],
            "format": "pdf",
        },
        "stress": {
            "title": "Stress Test Report",
            "sections": [
                "executive_summary",
                "scenarios_tested",
                "worst_case_analysis",
                "scenario_comparison",
                "breach_details",
                "recommendations",
                "methodology",
            ],
            "format": "pdf",
        },
        "audit": {
            "title": "Risk Audit Report",
            "sections": [
                "audit_summary",
                "compliance_status",
                "limit_breaches",
                "action_history",
                "system_health",
                "data_quality",
                "recommendations",
                "audit_trail",
            ],
            "format": "pdf",
        },
    }

    def __init__(self) -> None:
        self._custom_templates: dict[str, dict] = {}

    def get(self, template_name: str) -> Optional[dict[str, Any]]:
        """Get a template by name."""
        return self.TEMPLATES.get(template_name) or self._custom_templates.get(template_name)

    def list_templates(self) -> list[str]:
        """List all available templates."""
        return list(self.TEMPLATES.keys()) + list(self._custom_templates.keys())

    def add_custom(self, name: str, template: dict[str, Any]) -> None:
        """Add a custom template."""
        self._custom_templates[name] = template

    def render(self, template_name: str, data: dict[str, Any]) -> dict[str, Any]:
        """
        Render a report from template and data.

        Returns a structured dict representing the report content.
        """
        template = self.get(template_name)
        if not template:
            return {"error": f"Template '{template_name}' not found"}

        sections_rendered = {}
        for section in template.get("sections", []):
            renderer = getattr(self, f"_render_{section}", self._render_default)
            sections_rendered[section] = renderer(section, data)

        return {
            "report_title": template["title"],
            "template": template_name,
            "format": template.get("format", "json"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sections": sections_rendered,
        }

    # ---- Section Renderers ----

    def _render_executive_summary(self, section: str, data: dict) -> dict:
        return {
            "title": "Executive Summary",
            "overall_status": data.get("overall_status", "unknown"),
            "key_metrics": {
                "portfolio_value": data.get("portfolio_value", 0),
                "daily_pnl": data.get("daily_pnl", 0),
                "var_95": data.get("var_95_1d", 0),
            },
        }

    def _render_pnl_summary(self, section: str, data: dict) -> dict:
        return {
            "title": "P&L Summary",
            "daily_pnl": data.get("daily_pnl", 0),
            "daily_pnl_pct": data.get("daily_pnl_pct", 0),
            "mtd_pnl": data.get("mtd_pnl", 0),
            "ytd_pnl": data.get("ytd_pnl", 0),
        }

    def _render_var_cvar(self, section: str, data: dict) -> dict:
        return {
            "title": "VaR / CVaR",
            "var_95_1d": data.get("var_95_1d", 0),
            "var_99_1d": data.get("var_99_1d", 0),
            "cvar_95": data.get("cvar_95", 0),
        }

    def _render_exposure(self, section: str, data: dict) -> dict:
        return {
            "title": "Exposure",
            "gross": data.get("exposure_gross", 0),
            "net": data.get("exposure_net", 0),
        }

    def _render_alerts(self, section: str, data: dict) -> dict:
        return {
            "title": "Alerts",
            "active": data.get("active_alerts", 0),
            "critical": data.get("critical_alerts", 0),
        }

    def _render_drawdown(self, section: str, data: dict) -> dict:
        return {
            "title": "Drawdown",
            "current_pct": data.get("current_drawdown_pct", 0),
            "max_pct": data.get("max_drawdown_pct", 0),
        }

    def _render_stress_tests(self, section: str, data: dict) -> dict:
        return {
            "title": "Stress Tests",
            "scenarios_run": data.get("total_scenarios", 0),
            "passed": data.get("stress_passed", 0),
            "failed": data.get("stress_failed", 0),
            "worst_case": data.get("worst_stress_scenario", ""),
            "worst_loss_pct": data.get("worst_stress_loss_pct", 0),
        }

    def _render_attribution(self, section: str, data: dict) -> dict:
        return {
            "title": "Risk Attribution",
            "attribution": data.get("attribution", {}),
        }

    def _render_capital_adequacy(self, section: str, data: dict) -> dict:
        return {
            "title": "Capital Adequacy",
            "capital_ratio": data.get("capital_ratio", 0),
            "capital_surplus": data.get("capital_surplus", 0),
            "regulatory_status": data.get("regulatory_status", "unknown"),
        }

    def _render_recommendations(self, section: str, data: dict) -> dict:
        return {
            "title": "Recommendations",
            "items": data.get("recommendations", []),
        }

    def _render_default(self, section: str, data: dict) -> dict:
        return {"title": section.replace("_", " ").title(), "data": data.get(section, {})}
