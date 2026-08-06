"""Portfolio Report Generator — produce comprehensive portfolio research reports.

Generates multi-section reports covering:
* Portfolio Summary
* Optimization Results
* Risk Analysis
* Exposure Breakdown
* Stress Testing
* Scenario Analysis
* Attribution
* Turnover & Costs

Supports HTML, JSON, and PDF (reserved) output formats.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PortfolioReportFormat(str, Enum):
    """Supported report output formats."""

    JSON = "json"
    HTML = "html"
    PDF = "pdf"  # reserved


class PortfolioReportGenerator:
    """Generate comprehensive portfolio research reports.

    Outputs structured reports with scores and recommendations
    for portfolio quality assessment.
    """

    def __init__(self) -> None:
        self._title: str = "ICYQuant Portfolio Research Report"

    async def generate(
        self,
        portfolio: Dict[str, Any],
        analysis: Dict[str, Any],
        format: PortfolioReportFormat = PortfolioReportFormat.JSON,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a portfolio research report.

        Args:
            portfolio: Portfolio data with weights, universe, etc.
            analysis: Analysis results (risk, attribution, stress, etc.).
            format: Output format.
            title: Report title override.

        Returns:
            Report dict with sections and metadata.
        """
        if title:
            self._title = title

        sections = self._build_sections(portfolio, analysis)
        scores = self._compute_scores(sections)
        recommendation = self._make_recommendation(scores)

        report = {
            "meta": {
                "title": self._title,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "version": "1.0.0",
                "portfolio_id": portfolio.get("id", ""),
                "portfolio_name": portfolio.get("name", ""),
                "format": format.value,
            },
            "scores": scores,
            "recommendation": recommendation,
            "sections": sections,
        }

        if format == PortfolioReportFormat.HTML:
            report["html"] = self._render_html(report)

        return report

    def _build_sections(
        self, portfolio: Dict[str, Any], analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build report sections."""
        sections: List[Dict[str, Any]] = []

        # 1. Portfolio Summary
        sections.append(self._section_summary(portfolio, analysis))

        # 2. Optimization
        if "optimization" in analysis:
            sections.append(self._section_optimization(analysis["optimization"]))

        # 3. Risk Analysis
        if "risk" in analysis:
            sections.append(self._section_risk(analysis["risk"]))

        # 4. Exposure
        risk = analysis.get("risk", {})
        if "exposure" in risk:
            sections.append(self._section_exposure(risk["exposure"]))

        # 5. Stress Testing
        if "stress_test" in analysis:
            sections.append(self._section_stress(analysis["stress_test"]))

        # 6. Scenario Analysis
        if "scenarios" in analysis:
            sections.append(self._section_scenarios(analysis["scenarios"]))

        # 7. Attribution
        if "attribution" in analysis:
            sections.append(self._section_attribution(analysis["attribution"]))

        # 8. Statistics
        if "statistics" in analysis:
            sections.append(self._section_statistics(analysis["statistics"]))

        return sections

    def _section_summary(
        self, portfolio: Dict[str, Any], analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        weights = portfolio.get("weights", {})
        return {
            "title": "Portfolio Summary",
            "type": "summary",
            "data": {
                "name": portfolio.get("name", "Unnamed"),
                "category": portfolio.get("category", "long_only"),
                "optimizer": portfolio.get("optimizer", "unknown"),
                "num_assets": len(weights),
                "total_weight": sum(weights.values()),
                "top_holdings": sorted(
                    weights.items(), key=lambda x: x[1], reverse=True
                )[:10],
                "benchmark": portfolio.get("benchmark", "CSI300"),
            },
        }

    def _section_optimization(
        self, opt: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {
            "title": "Optimization Results",
            "type": "optimization",
            "data": {
                "optimizer_type": opt.get("optimizer_type", "unknown"),
                "status": opt.get("status", "unknown"),
                "expected_return": opt.get("expected_return", 0.0),
                "expected_risk": opt.get("expected_risk", 0.0),
                "sharpe_ratio": opt.get("sharpe_ratio", 0.0),
                "constraints_satisfied": opt.get(
                    "constraints_satisfied", True
                ),
                "messages": opt.get("messages", []),
            },
        }

    def _section_risk(self, risk: Dict[str, Any]) -> Dict[str, Any]:
        data: Dict[str, Any] = {}

        # Factor risk
        fr = risk.get("factor_risk", {}).get("to_dict", lambda: risk["factor_risk"])()
        if isinstance(fr, dict):
            data["factor_risk"] = {
                "total_risk": fr.get("total_risk", 0.0),
                "systematic_pct": fr.get("systematic_pct", 0.0),
            }

        # Tracking error
        te = risk.get("tracking_error", {}).get("to_dict", lambda: risk["tracking_error"])()
        if isinstance(te, dict):
            data["tracking_error"] = te.get("tracking_error_annual", 0.0)
            data["information_ratio"] = te.get("information_ratio", 0.0)
            data["active_share"] = te.get("active_share", 0.0)

        # VaR
        var_data = risk.get("var", {}).get("to_dict", lambda: risk["var"])()
        if isinstance(var_data, dict):
            data["var"] = var_data

        # CVaR
        cvar_data = risk.get("cvar", {}).get("to_dict", lambda: risk["cvar"])()
        if isinstance(cvar_data, dict):
            data["cvar"] = cvar_data

        return {
            "title": "Risk Analysis",
            "type": "risk",
            "data": data,
        }

    def _section_exposure(self, exposure: Dict[str, Any]) -> Dict[str, Any]:
        data = exposure.get("to_dict", lambda: exposure)()
        return {
            "title": "Exposure Analysis",
            "type": "exposure",
            "data": data if isinstance(data, dict) else {},
        }

    def _section_stress(self, stress: Dict[str, Any]) -> Dict[str, Any]:
        data = stress.get("to_dict", lambda: stress)()
        return {
            "title": "Stress Testing",
            "type": "stress_test",
            "data": data if isinstance(data, dict) else {},
        }

    def _section_scenarios(self, scenarios: Dict[str, Any]) -> Dict[str, Any]:
        data = scenarios.get("to_dict", lambda: scenarios)()
        return {
            "title": "Scenario Analysis",
            "type": "scenario",
            "data": data if isinstance(data, dict) else {},
        }

    def _section_attribution(self, attribution: Dict[str, Any]) -> Dict[str, Any]:
        data = attribution.get("to_dict", lambda: attribution)()
        return {
            "title": "Return Attribution",
            "type": "attribution",
            "data": data if isinstance(data, dict) else {},
        }

    def _section_statistics(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        data = stats.get("to_dict", lambda: stats)()
        return {
            "title": "Portfolio Statistics",
            "type": "statistics",
            "data": data if isinstance(data, dict) else {},
        }

    def _compute_scores(
        self, sections: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Compute quality scores for the portfolio."""
        scores: Dict[str, float] = {
            "overall": 5.0,
            "diversification": 5.0,
            "risk_management": 5.0,
            "efficiency": 5.0,
            "robustness": 5.0,
        }

        # Score diversification from summary
        for sec in sections:
            if sec.get("type") == "summary":
                n = sec.get("data", {}).get("num_assets", 0)
                if n < 5:
                    scores["diversification"] = 3.0
                elif n < 15:
                    scores["diversification"] = 5.0
                elif n < 30:
                    scores["diversification"] = 7.0
                else:
                    scores["diversification"] = 8.0

            # Score efficiency from optimization
            if sec.get("type") == "optimization":
                sharpe = sec.get("data", {}).get("sharpe_ratio", 0)
                if sharpe > 1.5:
                    scores["efficiency"] = 9.0
                elif sharpe > 1.0:
                    scores["efficiency"] = 7.0
                elif sharpe > 0.5:
                    scores["efficiency"] = 5.0
                else:
                    scores["efficiency"] = 3.0

            # Score risk from risk analysis
            if sec.get("type") == "risk":
                data = sec.get("data", {})
                stress = data.get("stress_test", {})

        # Overall
        scores["overall"] = sum(
            scores[k]
            for k in ["diversification", "risk_management", "efficiency", "robustness"]
        ) / 4.0

        return {k: round(v, 1) for k, v in scores.items()}

    def _make_recommendation(self, scores: Dict[str, float]) -> Dict[str, Any]:
        """Generate recommendation based on scores."""
        overall = scores["overall"]

        if overall >= 8.0:
            tier = "STRONG"
            action = "Ready for live deployment consideration"
        elif overall >= 6.0:
            tier = "PROMISING"
            action = "Further refinement recommended"
        elif overall >= 4.0:
            tier = "MARGINAL"
            action = "Significant improvements needed"
        else:
            tier = "REJECT"
            action = "Does not meet minimum quality standards"

        return {
            "tier": tier,
            "overall_score": overall,
            "action": action,
            "details": {
                "diversification": scores["diversification"],
                "risk_management": scores["risk_management"],
                "efficiency": scores["efficiency"],
                "robustness": scores["robustness"],
            },
        }

    def _render_html(self, report: Dict[str, Any]) -> str:
        """Render report as HTML."""
        meta = report.get("meta", {})
        scores = report.get("scores", {})
        rec = report.get("recommendation", {})

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{meta.get('title', 'Portfolio Report')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
        h1 {{ color: #1a5276; }}
        h2 {{ color: #2e86c1; border-bottom: 2px solid #2e86c1; }}
        .score {{ font-size: 24px; font-weight: bold; }}
        .tier-STLONG {{ color: green; }}
        .tier-PROMISING {{ color: blue; }}
        .tier-MARGINAL {{ color: orange; }}
        .tier-REJECT {{ color: red; }}
        table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
<h1>{meta.get('title', 'Portfolio Report')}</h1>
<p>Generated: {meta.get('generated_at', '')} | Portfolio: {meta.get('portfolio_name', '')}</p>
<h2>Overall Score: <span class="score">{scores.get('overall', 'N/A')}/10</span></h2>
<p>Recommendation: <strong class="tier-{rec.get('tier', '')}">{rec.get('tier', '')}</strong> — {rec.get('action', '')}</p>
<h2>Score Breakdown</h2>
<table>
    <tr><th>Category</th><th>Score</th></tr>
    <tr><td>Diversification</td><td>{scores.get('diversification', '-')}</td></tr>
    <tr><td>Risk Management</td><td>{scores.get('risk_management', '-')}</td></tr>
    <tr><td>Efficiency</td><td>{scores.get('efficiency', '-')}</td></tr>
    <tr><td>Robustness</td><td>{scores.get('robustness', '-')}</td></tr>
</table>
<p><em>Generated by ICYQuant Portfolio Research Engine</em></p>
</body>
</html>"""
        return html
