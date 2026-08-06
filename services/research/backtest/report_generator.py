"""Backtest Report Generator — automated comprehensive backtest report.

Generates multi-section reports with performance, risk, trading
statistics, drawdowns, monthly returns, benchmark comparison,
and attribution analysis.

Sections::

    Performance Summary → Risk Metrics → Trade Statistics → Drawdown
    → Monthly Return → Benchmark → Attribution → Summary

Output Formats: JSON (default), HTML (structured), PDF (reserved)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReportFormat(str, Enum):
    """Supported report output formats."""

    JSON = "json"
    HTML = "html"
    PDF = "pdf"  # reserved


class ReportSection(str, Enum):
    """Standard report sections."""

    PERFORMANCE = "performance"
    RISK = "risk"
    TRADE_STATISTICS = "trade_statistics"
    DRAWDOWN = "drawdown"
    MONTHLY_RETURNS = "monthly_returns"
    BENCHMARK = "benchmark"
    ATTRIBUTION = "attribution"
    EQUITY_CURVE = "equity_curve"
    CONFIG = "config"
    SUMMARY = "summary"
    ALL = "all"


class ReportGenerator:
    """Automated backtest report generator.

    Generates comprehensive reports with configurable sections,
    multiple output formats, and professional scoring.

    Usage::

        generator = ReportGenerator()
        report = await generator.generate(
            backtest_id="bt-001",
            performance=metrics.to_dict(),
            trades=trades,
            equity_curve=equity,
            format=ReportFormat.JSON,
        )
    """

    def __init__(self) -> None:
        self._sections: Dict[str, Any] = {}
        self._generated_count = 0

    # ── generation ─────────────────────────────────────────────────────────

    async def generate(
        self,
        backtest_id: str,
        performance: Optional[Dict[str, Any]] = None,
        trades: Optional[List[Dict[str, Any]]] = None,
        equity_curve: Optional[List[Dict[str, Any]]] = None,
        attribution: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
        sections: Optional[List[str]] = None,
        fmt: ReportFormat = ReportFormat.JSON,
    ) -> Dict[str, Any]:
        """Generate a complete backtest report.

        Args:
            backtest_id: Unique backtest identifier.
            performance: Performance metrics dict.
            trades: Trade records list.
            equity_curve: Equity curve data.
            attribution: Attribution result dict.
            config: Backtest configuration.
            sections: Specific sections to include.
            fmt: Output format.

        Returns:
            Complete report dictionary.
        """
        sections = sections or [ReportSection.ALL.value]
        include_all = ReportSection.ALL.value in sections

        report = {
            "backtest_id": backtest_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "format": fmt.value,
            "sections": {},
        }

        # Performance summary
        if include_all or ReportSection.PERFORMANCE.value in sections:
            report["sections"]["performance"] = self._build_performance_section(performance)

        # Risk metrics
        if include_all or ReportSection.RISK.value in sections:
            report["sections"]["risk"] = self._build_risk_section(performance)

        # Trade statistics
        if include_all or ReportSection.TRADE_STATISTICS.value in sections:
            report["sections"]["trade_statistics"] = self._build_trade_section(trades)

        # Drawdown
        if include_all or ReportSection.DRAWDOWN.value in sections:
            report["sections"]["drawdown"] = self._build_drawdown_section(performance)

        # Monthly returns
        if include_all or ReportSection.MONTHLY_RETURNS.value in sections:
            report["sections"]["monthly_returns"] = self._build_monthly_section(equity_curve)

        # Benchmark comparison
        if include_all or ReportSection.BENCHMARK.value in sections:
            report["sections"]["benchmark"] = self._build_benchmark_section(performance)

        # Attribution
        if include_all or ReportSection.ATTRIBUTION.value in sections:
            report["sections"]["attribution"] = self._build_attribution_section(attribution)

        # Equity curve
        if include_all or ReportSection.EQUITY_CURVE.value in sections:
            report["sections"]["equity_curve"] = equity_curve

        # Config
        if include_all or ReportSection.CONFIG.value in sections:
            report["sections"]["config"] = config

        # Summary and scoring
        if include_all or ReportSection.SUMMARY.value in sections:
            report["sections"]["summary"] = self._build_summary(report["sections"])

        self._generated_count += 1
        logger.info("Backtest report generated: %s (%d sections)", backtest_id[:8], len(report["sections"]))

        return report

    # ── section builders ───────────────────────────────────────────────────

    def _build_performance_section(
        self, performance: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not performance:
            return {}
        return {
            "total_return": performance.get("total_return", 0),
            "annual_return": performance.get("annual_return", 0),
            "cumulative_return": performance.get("cumulative_return", 0),
            "final_equity": performance.get("final_equity", 0),
            "total_days": performance.get("total_days", 0),
            "best_day": performance.get("best_day", 0),
            "worst_day": performance.get("worst_day", 0),
            "positive_days": performance.get("positive_days", 0),
            "negative_days": performance.get("negative_days", 0),
            "positive_day_ratio": performance.get("positive_days", 0) / max(performance.get("total_days", 1), 1),
        }

    def _build_risk_section(
        self, performance: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not performance:
            return {}
        return {
            "volatility": performance.get("volatility", 0),
            "downside_volatility": performance.get("downside_volatility", 0),
            "max_drawdown": performance.get("max_drawdown", 0),
            "max_drawdown_duration": performance.get("max_drawdown_duration", 0),
            "var_95": performance.get("var_95", 0),
            "cvar_95": performance.get("cvar_95", 0),
            "skewness": performance.get("skewness", 0),
            "kurtosis": performance.get("kurtosis", 0),
            "sharpe_ratio": performance.get("sharpe_ratio", 0),
            "sortino_ratio": performance.get("sortino_ratio", 0),
            "calmar_ratio": performance.get("calmar_ratio", 0),
            "information_ratio": performance.get("information_ratio", 0),
        }

    def _build_trade_section(
        self, trades: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        if not trades:
            return {"total_trades": 0, "win_rate": 0, "profit_factor": 0}
        from .statistics import compute_trade_statistics
        stats = compute_trade_statistics(trades)
        return stats.to_dict()

    def _build_drawdown_section(
        self, performance: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not performance:
            return {}
        max_dd = performance.get("max_drawdown", 0)
        severity = "SEVERE" if max_dd > 0.5 else "MODERATE" if max_dd > 0.2 else "MILD" if max_dd > 0.1 else "NONE"
        return {
            "max_drawdown": max_dd,
            "max_drawdown_pct": f"{max_dd * 100:.2f}%",
            "duration_days": performance.get("max_drawdown_duration", 0),
            "severity": severity,
        }

    def _build_monthly_section(
        self, equity_curve: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        if not equity_curve:
            return {}
        monthly: Dict[str, List[float]] = {}
        for e in equity_curve:
            ts = e.get("timestamp", "")
            if len(ts) >= 7:
                month = ts[:7]
                monthly.setdefault(month, []).append(e["equity"])

        result: Dict[str, float] = {}
        for month in sorted(monthly.keys()):
            values = monthly[month]
            if len(values) >= 2 and values[0] > 0:
                result[month] = (values[-1] - values[0]) / values[0]
        return {"monthly_returns": result, "months": len(result)}

    def _build_benchmark_section(
        self, performance: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not performance:
            return {}
        return {
            "benchmark_return": performance.get("benchmark_return", 0),
            "excess_return": performance.get("excess_return", 0),
            "tracking_error": performance.get("tracking_error", 0),
            "alpha": performance.get("alpha", 0),
            "beta": performance.get("beta", 0),
            "information_ratio": performance.get("information_ratio", 0),
        }

    def _build_attribution_section(
        self, attribution: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not attribution:
            return {}
        return {
            "total_return": attribution.get("total_return", 0),
            "excess_return": attribution.get("excess_return", 0),
            "allocation_effect": attribution.get("allocation_effect", 0),
            "selection_effect": attribution.get("selection_effect", 0),
            "interaction_effect": attribution.get("interaction_effect", 0),
            "factor_attribution": attribution.get("factor_attribution", {}),
            "timing_effect": attribution.get("timing_effect", 0),
            "residual": attribution.get("residual", 0),
        }

    def _build_summary(self, sections: Dict[str, Any]) -> Dict[str, Any]:
        """Generate overall summary and recommendation."""
        performance = sections.get("performance", {})
        risk = sections.get("risk", {})
        trade = sections.get("trade_statistics", {})

        sharpe = risk.get("sharpe_ratio", 0)
        max_dd = risk.get("max_drawdown", 0)
        win_rate = trade.get("win_rate", 0)
        annual_return = performance.get("annual_return", 0)

        # Scoring
        scores = []
        if sharpe > 1.5:
            scores.append(("Sharpe Ratio", "EXCELLENT", 5))
        elif sharpe > 1.0:
            scores.append(("Sharpe Ratio", "GOOD", 4))
        elif sharpe > 0.5:
            scores.append(("Sharpe Ratio", "ACCEPTABLE", 3))
        elif sharpe > 0:
            scores.append(("Sharpe Ratio", "WEAK", 2))
        else:
            scores.append(("Sharpe Ratio", "POOR", 1))

        if max_dd < 0.1:
            scores.append(("Drawdown Control", "EXCELLENT", 5))
        elif max_dd < 0.2:
            scores.append(("Drawdown Control", "GOOD", 4))
        elif max_dd < 0.3:
            scores.append(("Drawdown Control", "ACCEPTABLE", 3))
        elif max_dd < 0.5:
            scores.append(("Drawdown Control", "WEAK", 2))
        else:
            scores.append(("Drawdown Control", "POOR", 1))

        if win_rate > 0.6:
            scores.append(("Win Rate", "EXCELLENT", 5))
        elif win_rate > 0.55:
            scores.append(("Win Rate", "GOOD", 4))
        elif win_rate > 0.5:
            scores.append(("Win Rate", "ACCEPTABLE", 3))
        elif win_rate > 0.4:
            scores.append(("Win Rate", "WEAK", 2))
        else:
            scores.append(("Win Rate", "POOR", 1))

        avg_score = sum(s[2] for s in scores) / len(scores) if scores else 0

        if avg_score >= 4:
            recommendation = "STRONG — Ready for production consideration"
        elif avg_score >= 3:
            recommendation = "PROMISING — Needs further validation"
        elif avg_score >= 2:
            recommendation = "MARGINAL — Requires significant improvement"
        else:
            recommendation = "REJECT — Not viable as standalone strategy"

        return {
            "recommendation": recommendation,
            "overall_score": avg_score,
            "scores": {s[0]: {"rating": s[1], "score": s[2]} for s in scores},
            "key_metrics": {
                "annual_return": annual_return,
                "sharpe_ratio": sharpe,
                "max_drawdown": max_dd,
                "win_rate": win_rate,
            },
        }

    # ── export ─────────────────────────────────────────────────────────────

    def export_json(self, report: Dict[str, Any]) -> str:
        """Export report as JSON string."""
        return json.dumps(report, indent=2, default=str, ensure_ascii=False)

    def export_html(self, report: Dict[str, Any]) -> str:
        """Export report as an HTML string."""
        sections_html = ""
        for name, data in report.get("sections", {}).items():
            sections_html += f"<h2>{name.replace('_', ' ').title()}</h2>\n"
            sections_html += f"<pre>{json.dumps(data, indent=2, default=str)}</pre>\n"

        return f"""<!DOCTYPE html>
<html><head><title>Backtest Report - {report.get('backtest_id', 'N/A')[:8]}</title>
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }}
h1 {{ color: #333; }} h2 {{ color: #555; border-bottom: 2px solid #eee; padding-bottom: 8px; }}
pre {{ background: #f5f5f5; padding: 15px; border-radius: 5px; overflow-x: auto; font-size: 13px; }}
</style></head>
<body>
<h1>ICYQuant Backtest Report</h1>
<p>Backtest ID: {report.get('backtest_id', 'N/A')[:8]}</p>
<p>Generated: {report.get('generated_at', 'N/A')}</p>
{sections_html}
</body></html>"""

    def get_stats(self) -> Dict[str, Any]:
        """Return report generator statistics."""
        return {
            "generated_count": self._generated_count,
        }
