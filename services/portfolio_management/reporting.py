"""Reporting Engine — portfolio reports, templates, and multi-format export."""

import time
import uuid
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReportType(Enum):
    DAILY_SUMMARY = "daily_summary"
    WEEKLY_REVIEW = "weekly_review"
    MONTHLY_REPORT = "monthly_report"
    QUARTERLY_REVIEW = "quarterly_review"
    ANNUAL_REPORT = "annual_report"
    PERFORMANCE_ATTRIBUTION = "performance_attribution"
    RISK_REPORT = "risk_report"
    CAPITAL_ALLOCATION = "capital_allocation"
    COMPLIANCE = "compliance"
    INVESTOR_LETTER = "investor_letter"
    BOARD_REPORT = "board_report"
    CUSTOM = "custom"


class ExportFormat(Enum):
    PDF = "pdf"
    HTML = "html"
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"
    MARKDOWN = "markdown"


@dataclass
class ReportConfig:
    """Configuration for report generation."""

    default_format: ExportFormat = ExportFormat.PDF
    include_charts: bool = True
    include_tables: bool = True
    include_disclaimer: bool = True
    language: str = "zh-CN"  # zh-CN | en-US
    timezone: str = "Asia/Shanghai"
    branding: Dict[str, str] = field(default_factory=lambda: {
        "firm_name": "ICYQuant",
        "logo_url": "",
        "primary_color": "#1a73e8",
    })
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportSection:
    """A section within a report."""

    section_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    order: int = 0
    content: Dict[str, Any] = field(default_factory=dict)
    charts: List[str] = field(default_factory=list)  # chart references
    tables: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportTemplate:
    """A report template with predefined sections."""

    template_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    report_type: ReportType = ReportType.CUSTOM
    sections: List[ReportSection] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PortfolioReport:
    """A generated portfolio report."""

    report_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8]
    )
    report_type: ReportType = ReportType.MONTHLY_REPORT
    title: str = ""
    portfolio_ids: List[str] = field(default_factory=list)
    period_start: str = ""
    period_end: str = ""
    generated_at: float = field(default_factory=time.time)
    sections: List[ReportSection] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    export_formats: List[ExportFormat] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ReportingEngine:
    """Generates portfolio reports in multiple formats.

    Supports:
    - Multiple report types (daily, weekly, monthly, quarterly, annual)
    - Customizable templates and sections
    - Multi-format export (PDF, HTML, CSV, JSON, Excel, Markdown)
    - Performance attribution reports
    - Risk reports
    - Investor letters

    """

    def __init__(self, config: Optional[ReportConfig] = None):
        self.config = config or ReportConfig()
        self._templates: Dict[str, ReportTemplate] = {}
        self._reports: List[PortfolioReport] = []

    def create_template(
        self, name: str, report_type: ReportType, sections: Optional[List[ReportSection]] = None
    ) -> ReportTemplate:
        template = ReportTemplate(
            name=name,
            report_type=report_type,
            sections=sections or [],
        )
        self._templates[template.template_id] = template
        return template

    def create_default_templates(self) -> Dict[str, ReportTemplate]:
        """Create standard report templates."""
        templates = {}

        # Monthly Report
        monthly = self.create_template(
            "Monthly Portfolio Report",
            ReportType.MONTHLY_REPORT,
            sections=[
                ReportSection(title="Executive Summary", order=1),
                ReportSection(title="Performance Overview", order=2),
                ReportSection(title="Risk Analysis", order=3),
                ReportSection(title="Attribution Analysis", order=4),
                ReportSection(title="Position Summary", order=5),
                ReportSection(title="Capital Allocation", order=6),
                ReportSection(title="Market Commentary", order=7),
                ReportSection(title="Outlook & Positioning", order=8),
                ReportSection(title="Disclaimer", order=9),
            ],
        )
        templates["monthly"] = monthly

        # Risk Report
        risk = self.create_template(
            "Risk Report",
            ReportType.RISK_REPORT,
            sections=[
                ReportSection(title="Risk Summary", order=1),
                ReportSection(title="VaR & CVaR Analysis", order=2),
                ReportSection(title="Stress Testing Results", order=3),
                ReportSection(title="Risk Budget Utilization", order=4),
                ReportSection(title="Concentration Analysis", order=5),
                ReportSection(title="Counterparty Risk", order=6),
                ReportSection(title="Liquidity Risk", order=7),
            ],
        )
        templates["risk"] = risk

        # Attribution Report
        attribution = self.create_template(
            "Performance Attribution Report",
            ReportType.PERFORMANCE_ATTRIBUTION,
            sections=[
                ReportSection(title="Attribution Summary", order=1),
                ReportSection(title="Brinson Decomposition", order=2),
                ReportSection(title="Sector Attribution", order=3),
                ReportSection(title="Factor Attribution", order=4),
                ReportSection(title="Top/Bottom Contributors", order=5),
                ReportSection(title="Attribution Quality Metrics", order=6),
            ],
        )
        templates["attribution"] = attribution

        return templates

    def generate_report(
        self,
        report_type: ReportType,
        title: str,
        portfolio_ids: List[str],
        data: Dict[str, Any],
        template_id: Optional[str] = None,
        period_start: str = "",
        period_end: str = "",
    ) -> PortfolioReport:
        """Generate a report from data and template."""

        # Get template sections
        sections = []
        if template_id and template_id in self._templates:
            sections = [
                ReportSection(
                    title=s.title,
                    order=s.order,
                    content=self._populate_section_content(s.title, data),
                )
                for s in self._templates[template_id].sections
            ]
        else:
            # Default: one summary section
            sections = [
                ReportSection(
                    title="Report Summary",
                    order=0,
                    content=data,
                )
            ]

        report = PortfolioReport(
            report_type=report_type,
            title=title,
            portfolio_ids=portfolio_ids,
            period_start=period_start,
            period_end=period_end,
            sections=sections,
            summary={
                "generated_by": self.config.branding.get("firm_name", "ICYQuant"),
                "language": self.config.language,
                "timezone": self.config.timezone,
            },
            export_formats=[self.config.default_format],
        )

        self._reports.append(report)
        logger.info(
            "Report generated: %s (%s) for %d portfolio(s)",
            title, report_type.value, len(portfolio_ids),
        )
        return report

    def _populate_section_content(
        self, section_title: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Populate section content from data based on section title."""
        mapping = {
            "Executive Summary": data.get("summary", {}),
            "Performance Overview": data.get("performance", {}),
            "Risk Analysis": data.get("risk", {}),
            "Attribution Analysis": data.get("attribution", {}),
            "Attribution Summary": data.get("attribution", {}),
            "Position Summary": data.get("positions", {}),
            "Capital Allocation": data.get("allocation", {}),
            "Market Commentary": data.get("commentary", {}),
            "Risk Summary": data.get("risk", {}),
            "VaR & CVaR Analysis": data.get("var", {}),
            "Risk Budget Utilization": data.get("risk_budget", {}),
            "Concentration Analysis": data.get("concentration", {}),
        }
        return mapping.get(section_title, data)

    def export_report(
        self,
        report_id: str,
        format: Optional[ExportFormat] = None,
    ) -> Optional[str]:
        """Export a report to the specified format."""
        report = self._get_report(report_id)
        if not report:
            return None

        format = format or self.config.default_format

        if format == ExportFormat.JSON:
            return self._export_json(report)
        elif format == ExportFormat.CSV:
            return self._export_csv(report)
        elif format == ExportFormat.MARKDOWN:
            return self._export_markdown(report)
        elif format == ExportFormat.HTML:
            return self._export_html(report)
        else:
            # Default to JSON for PDF/Excel (would need external libraries)
            logger.warning("Export format %s requires external library, using JSON fallback", format.value)
            return self._export_json(report)

    def _export_json(self, report: PortfolioReport) -> str:
        return json.dumps({
            "report_id": report.report_id,
            "report_type": report.report_type.value,
            "title": report.title,
            "portfolio_ids": report.portfolio_ids,
            "period_start": report.period_start,
            "period_end": report.period_end,
            "generated_at": report.generated_at,
            "sections": [
                {"title": s.title, "content": s.content, "order": s.order}
                for s in report.sections
            ],
            "summary": report.summary,
        }, ensure_ascii=False, indent=2)

    def _export_csv(self, report: PortfolioReport) -> str:
        """Export report as CSV (flattened sections)."""
        lines = ["section,key,value"]
        for section in report.sections:
            for key, value in section.content.items():
                if isinstance(value, (int, float, str)):
                    lines.append(f'"{section.title}","{key}","{value}"')
        return "\n".join(lines)

    def _export_markdown(self, report: PortfolioReport) -> str:
        """Export report as Markdown."""
        lines = [
            f"# {report.title}",
            f"",
            f"**Report Type:** {report.report_type.value}",
            f"**Portfolios:** {', '.join(report.portfolio_ids)}",
            f"**Period:** {report.period_start} to {report.period_end}",
            f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(report.generated_at))}",
            f"",
            f"---",
            f"",
        ]

        for section in sorted(report.sections, key=lambda s: s.order):
            lines.append(f"## {section.title}")
            lines.append("")
            if isinstance(section.content, dict):
                for key, value in section.content.items():
                    if isinstance(value, dict):
                        lines.append(f"### {key}")
                        lines.append("")
                        for k, v in value.items():
                            if isinstance(v, float):
                                lines.append(f"- **{k}:** {v:.4f}")
                            else:
                                lines.append(f"- **{k}:** {v}")
                        lines.append("")
                    elif isinstance(value, list):
                        lines.append(f"- **{key}:** {len(value)} items")
                    else:
                        lines.append(f"- **{key}:** {value}")
            lines.append("")

        lines.append("---")
        lines.append(f"*Report generated by {self.config.branding.get('firm_name', 'ICYQuant')}*")
        if self.config.include_disclaimer:
            lines.append("")
            lines.append("*Disclaimer: This report is for informational purposes only and does not constitute investment advice.*")

        return "\n".join(lines)

    def _export_html(self, report: PortfolioReport) -> str:
        """Export report as HTML."""
        primary_color = self.config.branding.get("primary_color", "#1a73e8")

        html = [
            "<!DOCTYPE html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="UTF-8">',
            f"<title>{report.title}</title>",
            "<style>",
            f"body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; color: #333; }}",
            f"h1 {{ color: {primary_color}; border-bottom: 2px solid {primary_color}; padding-bottom: 10px; }}",
            f"h2 {{ color: {primary_color}; margin-top: 30px; }}",
            f"h3 {{ color: #555; }}",
            f".meta {{ color: #666; font-size: 14px; margin-bottom: 20px; }}",
            f"table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}",
            f"th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}",
            f"th {{ background-color: #f5f5f5; }}",
            f".metric {{ font-weight: bold; }}",
            f".positive {{ color: #2e7d32; }}",
            f".negative {{ color: #c62828; }}",
            f".disclaimer {{ color: #999; font-size: 12px; margin-top: 30px; border-top: 1px solid #eee; padding-top: 10px; }}",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>{report.title}</h1>",
            '<div class="meta">',
            f"<p><strong>Type:</strong> {report.report_type.value} | "
            f"<strong>Portfolios:</strong> {', '.join(report.portfolio_ids)}</p>",
            f"<p><strong>Period:</strong> {report.period_start} to {report.period_end} | "
            f"<strong>Generated:</strong> {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(report.generated_at))}</p>",
            "</div>",
        ]

        for section in sorted(report.sections, key=lambda s: s.order):
            html.append(f"<h2>{section.title}</h2>")
            if isinstance(section.content, dict):
                for key, value in section.content.items():
                    if isinstance(value, dict):
                        html.append(f"<h3>{key}</h3>")
                        html.append("<table><tr><th>Metric</th><th>Value</th></tr>")
                        for k, v in value.items():
                            if isinstance(v, float):
                                css_class = "positive" if v > 0 else "negative" if v < 0 else ""
                                html.append(
                                    f'<tr><td>{k}</td><td class="metric {css_class}">{v:.4f}</td></tr>'
                                )
                            else:
                                html.append(f"<tr><td>{k}</td><td>{v}</td></tr>")
                        html.append("</table>")
                    elif isinstance(v, list):
                        html.append(f"<p><strong>{key}:</strong> {len(v)} items</p>")
                    else:
                        html.append(f"<p><strong>{key}:</strong> {v}</p>")

        if self.config.include_disclaimer:
            html.append('<div class="disclaimer">')
            html.append("<p><strong>Disclaimer:</strong> This report is for informational purposes only and does not constitute investment advice. Past performance is not indicative of future results.</p>")
            html.append(f"<p>Generated by {self.config.branding.get('firm_name', 'ICYQuant')}</p>")
            html.append("</div>")

        html.append("</body></html>")
        return "\n".join(html)

    def _get_report(self, report_id: str) -> Optional[PortfolioReport]:
        for report in self._reports:
            if report.report_id == report_id:
                return report
        return None

    def get_report(self, report_id: str) -> Optional[PortfolioReport]:
        return self._get_report(report_id)

    def list_reports(
        self,
        report_type: Optional[ReportType] = None,
        limit: int = 50,
    ) -> List[PortfolioReport]:
        results = self._reports
        if report_type:
            results = [r for r in results if r.report_type == report_type]
        return results[-limit:]

    def get_template(self, template_id: str) -> Optional[ReportTemplate]:
        return self._templates.get(template_id)

    def list_templates(self) -> List[ReportTemplate]:
        return list(self._templates.values())

    def get_summary(self) -> Dict[str, Any]:
        reports = self._reports
        by_type: Dict[str, int] = {}
        for r in reports:
            t = r.report_type.value
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "total_reports": len(reports),
            "total_templates": len(self._templates),
            "default_format": self.config.default_format.value,
            "reports_by_type": by_type,
        }
