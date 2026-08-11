"""Reporting Agent — specialized agent for report generation, aggregation, and distribution.

Pipeline:
    Reporting request / Coordinator finalization
        -> ReportingAgent.gather_results() (collect from all agents)
        -> ReportingAgent.format_report() (structure report)
        -> ReportingAgent.generate() (produce final report)
        -> ReportingAgent.distribute() (publish to consumers)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.ai_agent.collaboration.message_bus import MessageBus, Message, MessageType

logger = logging.getLogger(__name__)


class ReportFormat(str, Enum):
    """Output formats for reports."""
    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"
    TEXT = "text"


class ReportSection(str, Enum):
    """Standard report sections."""
    EXECUTIVE_SUMMARY = "executive_summary"
    MARKET_OVERVIEW = "market_overview"
    RESEARCH_FINDINGS = "research_findings"
    RISK_ASSESSMENT = "risk_assessment"
    PORTFOLIO_STATUS = "portfolio_status"
    SIGNALS = "signals"
    RECOMMENDATIONS = "recommendations"
    APPENDIX = "appendix"


@dataclass
class Report:
    """A generated report.

    Attributes:
        report_id: Unique report identifier.
        title: Report title.
        sections: Report sections with content.
        format: Output format.
        generated_by: Agent that generated this report.
        created_at: Generation timestamp.
        metadata: Additional report metadata.
    """

    report_id: str = field(default_factory=lambda: uuid4().hex)
    title: str = ""
    sections: Dict[str, Any] = field(default_factory=dict)
    format: ReportFormat = ReportFormat.MARKDOWN
    generated_by: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_markdown(self) -> str:
        """Convert report to markdown format.

        Returns:
            Markdown string.
        """
        lines = [f"# {self.title}", f"\n*Generated: {self.created_at.isoformat()}*\n"]
        for section_name, content in self.sections.items():
            section_title = section_name.replace("_", " ").title()
            lines.append(f"## {section_title}")
            lines.append(str(content))
            lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Return report as a dictionary."""
        return {
            "report_id": self.report_id,
            "title": self.title,
            "sections": self.sections,
            "format": self.format.value,
            "created_at": self.created_at.isoformat(),
        }


class ReportingAgent:
    """Specialized agent for report generation and distribution.

    Collects results from all specialized agents, formats them into
    structured reports, and distributes to consumers.

    Supports:
        - Multi-source result aggregation
        - Structured report generation (JSON, Markdown, HTML, Text)
        - Executive summary generation
        - Report distribution
        - Historical report archiving

    Usage:
        agent = ReportingAgent(agent_id="report_1", message_bus=bus)
        await agent.initialize()
        report = await agent.generate(
            title="Daily Market Report",
            results=agent_results,
        )
    """

    def __init__(
        self,
        agent_id: str = "",
        message_bus: Optional[MessageBus] = None,
    ) -> None:
        """Initialize the Reporting Agent.

        Args:
            agent_id: Unique agent identifier.
            message_bus: Message bus for communication.
        """
        self._agent_id: str = agent_id or uuid4().hex[:12]
        self._message_bus: Optional[MessageBus] = message_bus
        self._initialized: bool = False
        self._reports: List[Report] = []
        logger.info("ReportingAgent created: %s", self._agent_id)

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the reporting agent."""
        if self._initialized:
            return
        self._initialized = True
        logger.info("ReportingAgent initialized: %s", self._agent_id)

    async def shutdown(self) -> None:
        """Shut down the reporting agent."""
        self._reports.clear()
        self._initialized = False
        logger.info("ReportingAgent shutdown: %s", self._agent_id)

    # ── Result Gathering ──

    async def gather_results(
        self, sources: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Gather results from multiple agent sources.

        Args:
            sources: Dictionary of agent_name -> result data.

        Returns:
            Aggregated results organized by section.
        """
        sections: Dict[str, Any] = {}

        section_mapping = {
            "market": ReportSection.MARKET_OVERVIEW,
            "research": ReportSection.RESEARCH_FINDINGS,
            "risk": ReportSection.RISK_ASSESSMENT,
            "portfolio": ReportSection.PORTFOLIO_STATUS,
            "strategy": ReportSection.SIGNALS,
            "macro": ReportSection.MARKET_OVERVIEW,
        }

        for source_name, data in sources.items():
            section = section_mapping.get(source_name, ReportSection.APPENDIX)
            sections[section.value] = data

        logger.debug("ReportingAgent gathered results from %d sources", len(sources))
        return sections

    # ── Report Generation ──

    async def generate(
        self,
        title: str,
        results: Dict[str, Any],
        fmt: ReportFormat = ReportFormat.MARKDOWN,
    ) -> Report:
        """Generate a report from agent results.

        Args:
            title: Report title.
            results: Aggregated results by section.
            fmt: Output format.

        Returns:
            Generated report.
        """
        # Generate executive summary
        summary = self._generate_summary(results)

        sections = {
            ReportSection.EXECUTIVE_SUMMARY.value: summary,
        }
        sections.update(results)

        report = Report(
            title=title,
            sections=sections,
            format=fmt,
            generated_by=self._agent_id,
        )
        self._reports.append(report)

        if self._message_bus:
            await self._message_bus.publish(Message(
                msg_type=MessageType.PUBLISH,
                topic="report.generated",
                sender_id=self._agent_id,
                payload={
                    "report_id": report.report_id,
                    "title": title,
                    "format": fmt.value,
                    "sections": list(sections.keys()),
                },
            ))

        logger.info("ReportingAgent generated: %s (%d sections)", title, len(sections))
        return report

    def _generate_summary(self, results: Dict[str, Any]) -> str:
        """Generate an executive summary from results.

        Args:
            results: Section results.

        Returns:
            Executive summary string.
        """
        parts: List[str] = ["Executive Summary:"]
        for section, content in results.items():
            if isinstance(content, dict):
                if "overall_level" in content:
                    parts.append(f"- Risk: {content['overall_level']}")
                elif "regime" in content:
                    parts.append(f"- Market: {content['regime']}")
                elif "metrics" in content:
                    parts.append(f"- Performance: {content['metrics']}")
            elif isinstance(content, str):
                parts.append(f"- {content[:100]}")
        return "\n".join(parts) if len(parts) > 1 else "No significant findings."

    # ── Distribution ──

    async def distribute(self, report: Report) -> None:
        """Distribute a report to all consumers.

        Args:
            report: The report to distribute.
        """
        if self._message_bus:
            await self._message_bus.broadcast(Message(
                msg_type=MessageType.BROADCAST,
                topic="report.distribute",
                sender_id=self._agent_id,
                payload=report.to_dict(),
            ))
        logger.info("ReportingAgent distributed report: %s", report.report_id)

    # ── Properties ──

    @property
    def agent_id(self) -> str:
        """Return the agent ID."""
        return self._agent_id

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the reporting agent state.

        Returns:
            Dict with report count.
        """
        return {
            "agent_id": self._agent_id,
            "initialized": self._initialized,
            "total_reports": len(self._reports),
        }
