"""
ICYQuant Report Generator — automated research report generation.

Produces structured, professional research reports with summaries,
charts, evidence, risk analysis, and conclusions from research pipeline output.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ReportFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"
    HTML = "html"
    PDF = "pdf"


class ReportStatus(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    PUBLISHED = "published"


@dataclass
class ResearchReport:
    """A complete research report."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    summary: str = ""
    question: str = ""
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    evidence_summary: dict[str, Any] = field(default_factory=dict)
    analysis: str = ""
    risk_assessment: str = ""
    conclusions: str = ""
    recommendations: list[str] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    charts: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    status: ReportStatus = ReportStatus.DRAFT
    format: ReportFormat = ReportFormat.JSON
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class ReportGenerator:
    """Automated research report generation engine.

    Generates structured reports following the pipeline:
        Research Summary → Charts → Evidence → Risk Analysis → Final Report

    Supports multiple output formats: Markdown, JSON, HTML, PDF.
    """

    def __init__(self) -> None:
        self._reports: dict[str, ResearchReport] = {}
        self._total_generated = 0

    async def generate(
        self,
        question: str,
        plan: list[dict[str, Any]],
        hypotheses: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        citations: list[dict[str, Any]],
        format: ReportFormat = ReportFormat.JSON,
    ) -> dict[str, Any]:
        """Generate a complete research report from pipeline output."""
        self._total_generated += 1

        report = ResearchReport(
            title=f"Research Report: {question[:80]}",
            question=question,
            hypotheses=hypotheses,
            evidence_summary=self._summarize_evidence(evidence),
            analysis=self._generate_analysis(question, hypotheses, evidence),
            risk_assessment=self._generate_risk_assessment(evidence),
            conclusions=self._generate_conclusions(hypotheses, evidence),
            recommendations=self._generate_recommendations(hypotheses, evidence),
            citations=citations,
            confidence=self._calculate_confidence(hypotheses, evidence),
            format=format,
        )

        self._reports[report.report_id] = report

        return self._serialize(report, format)

    def _summarize_evidence(self, evidence: list[dict[str, Any]]) -> dict[str, Any]:
        supporting = sum(1 for e in evidence if e.get("direction") == "supports")
        contradicting = sum(1 for e in evidence if e.get("direction") == "contradicts")
        neutral = sum(1 for e in evidence if e.get("direction") == "neutral")

        return {
            "total_items": len(evidence),
            "supporting": supporting,
            "contradicting": contradicting,
            "neutral": neutral,
            "net_support": supporting - contradicting,
        }

    def _generate_analysis(
        self,
        question: str,
        hypotheses: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> str:
        """Generate the analysis section."""
        h_count = len(hypotheses)
        e_count = len(evidence)
        summary = self._summarize_evidence(evidence)

        return (
            f"Analysis of research question: '{question}'\n\n"
            f"Generated {h_count} hypotheses and evaluated {e_count} pieces of evidence.\n"
            f"Supporting evidence: {summary['supporting']}, "
            f"Contradicting: {summary['contradicting']}, "
            f"Neutral: {summary['neutral']}.\n\n"
            f"Net evidence support: {summary['net_support']}."
        )

    def _generate_risk_assessment(self, evidence: list[dict[str, Any]]) -> str:
        """Generate the risk assessment section."""
        summary = self._summarize_evidence(evidence)
        net_support = summary["net_support"]

        if net_support > 5:
            risk_level = "Low"
        elif net_support > 0:
            risk_level = "Moderate"
        elif net_support == 0:
            risk_level = "Uncertain"
        else:
            risk_level = "High"

        return (
            f"Risk Level: {risk_level}\n"
            f"Evidence Quality: Based on {summary['total_items']} evidence items. "
            f"Confidence in conclusions is {'high' if risk_level == 'Low' else 'moderate' if risk_level == 'Moderate' else 'limited'}."
        )

    def _generate_conclusions(
        self,
        hypotheses: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> str:
        """Generate the conclusions section."""
        if not hypotheses:
            return "No hypotheses were generated for this research question."

        conclusions = ["Research Conclusions:"]
        for i, h in enumerate(hypotheses, 1):
            statement = h.get("statement", "Unknown hypothesis")
            confidence = h.get("confidence", 0.0)
            verdict = "supported" if confidence > 0.6 else "requires further investigation" if confidence > 0.3 else "not supported"
            conclusions.append(f"{i}. {statement} — {verdict} (confidence: {confidence:.2f})")

        return "\n".join(conclusions)

    def _generate_recommendations(
        self,
        hypotheses: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> list[str]:
        """Generate actionable recommendations."""
        recommendations = []
        summary = self._summarize_evidence(evidence)

        if summary["supporting"] > summary["contradicting"]:
            recommendations.append("Proceed with further investigation of supported hypotheses")
        else:
            recommendations.append("Re-evaluate research direction — evidence is inconclusive")

        if summary["total_items"] < 10:
            recommendations.append("Gather additional data to strengthen evidence base")

        recommendations.append("Document findings and share with research team for peer review")

        return recommendations

    def _calculate_confidence(
        self,
        hypotheses: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> float:
        """Calculate overall research confidence score."""
        if not hypotheses:
            return 0.0

        h_confidence = sum(h.get("confidence", 0.0) for h in hypotheses) / len(hypotheses)
        summary = self._summarize_evidence(evidence)
        e_ratio = summary["supporting"] / max(1, summary["total_items"])

        return round((h_confidence * 0.6 + e_ratio * 0.4), 2)

    def _serialize(self, report: ResearchReport, format: ReportFormat) -> dict[str, Any]:
        """Serialize report to the requested format."""
        if format == ReportFormat.JSON:
            return {
                "report_id": report.report_id,
                "title": report.title,
                "summary": report.summary,
                "question": report.question,
                "analysis": report.analysis,
                "risk_assessment": report.risk_assessment,
                "conclusions": report.conclusions,
                "recommendations": report.recommendations,
                "confidence": report.confidence,
                "hypotheses": report.hypotheses,
                "evidence_summary": report.evidence_summary,
                "citations": report.citations,
                "status": report.status.value,
                "format": report.format.value,
                "created_at": report.created_at.isoformat(),
            }
        elif format == ReportFormat.MARKDOWN:
            return {
                "report_id": report.report_id,
                "title": report.title,
                "format": "markdown",
                "content": self._to_markdown(report),
            }
        else:
            return {
                "report_id": report.report_id,
                "title": report.title,
                "format": report.format.value,
                "content": report.analysis,
            }

    def _to_markdown(self, report: ResearchReport) -> str:
        """Convert report to Markdown format."""
        md = f"# {report.title}\n\n"
        md += f"**Confidence**: {report.confidence:.0%}\n\n"
        md += f"## Summary\n\n{report.summary}\n\n"
        md += f"## Analysis\n\n{report.analysis}\n\n"
        md += f"## Risk Assessment\n\n{report.risk_assessment}\n\n"
        md += f"## Conclusions\n\n{report.conclusions}\n\n"

        if report.recommendations:
            md += "## Recommendations\n\n"
            for rec in report.recommendations:
                md += f"- {rec}\n"
            md += "\n"

        if report.citations:
            md += "## References\n\n"
            for i, c in enumerate(report.citations, 1):
                md += f"{i}. {c.get('title', 'Unknown')}\n"

        return md

    def get_report(self, report_id: str) -> Optional[ResearchReport]:
        return self._reports.get(report_id)

    def list_reports(self, limit: int = 50) -> list[ResearchReport]:
        reports = list(self._reports.values())
        reports.sort(key=lambda r: r.created_at, reverse=True)
        return reports[:limit]

    @property
    def total_generated(self) -> int:
        return self._total_generated
