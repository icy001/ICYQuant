"""
ICYQuant Template Registry — research report and output template management.

Manages structured output templates for research reports, ensuring
consistent formatting and quality across all research outputs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TemplateFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"
    HTML = "html"
    LATEX = "latex"


class TemplateCategory(str, Enum):
    RESEARCH_REPORT = "research_report"
    EXECUTIVE_SUMMARY = "executive_summary"
    FACTOR_ANALYSIS = "factor_analysis"
    STRATEGY_BACKTEST = "strategy_backtest"
    RISK_REPORT = "risk_report"
    MARKET_REVIEW = "market_review"
    EXPERIMENT_LOG = "experiment_log"


@dataclass
class Template:
    """A structured output template."""
    template_id: str
    name: str
    category: TemplateCategory
    format: TemplateFormat
    schema: dict[str, Any]  # JSON Schema for output structure
    description: str = ""
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    usage_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class TemplateRegistry:
    """Registry for research output templates.

    Responsibilities:
        - Template creation and versioning
        - Format-specific schemas (Markdown, JSON, HTML, LaTeX)
        - Output validation against templates
        - Default template provision for common report types
    """

    def __init__(self) -> None:
        self._templates: dict[str, Template] = {}
        self._category_index: dict[TemplateCategory, list[str]] = {
            c: [] for c in TemplateCategory
        }
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register built-in output templates."""
        defaults = [
            Template(
                template_id="research_report_v1",
                name="Standard Research Report",
                category=TemplateCategory.RESEARCH_REPORT,
                format=TemplateFormat.JSON,
                schema={
                    "type": "object",
                    "required": ["title", "summary", "sections", "conclusions"],
                    "properties": {
                        "title": {"type": "string"},
                        "summary": {"type": "string"},
                        "sections": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "heading": {"type": "string"},
                                    "content": {"type": "string"},
                                    "subsections": {"type": "array"},
                                },
                            },
                        },
                        "conclusions": {"type": "string"},
                        "citations": {"type": "array"},
                        "metadata": {"type": "object"},
                    },
                },
            ),
            Template(
                template_id="executive_summary_v1",
                name="Executive Summary",
                category=TemplateCategory.EXECUTIVE_SUMMARY,
                format=TemplateFormat.JSON,
                schema={
                    "type": "object",
                    "required": ["title", "key_findings", "recommendation"],
                    "properties": {
                        "title": {"type": "string"},
                        "key_findings": {"type": "array", "items": {"type": "string"}},
                        "recommendation": {"type": "string"},
                        "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
                        "confidence": {"type": "number"},
                    },
                },
            ),
            Template(
                template_id="factor_analysis_v1",
                name="Factor Analysis Report",
                category=TemplateCategory.FACTOR_ANALYSIS,
                format=TemplateFormat.JSON,
                schema={
                    "type": "object",
                    "required": ["factor_name", "analysis", "performance"],
                    "properties": {
                        "factor_name": {"type": "string"},
                        "analysis": {"type": "string"},
                        "performance": {
                            "type": "object",
                            "properties": {
                                "sharpe_ratio": {"type": "number"},
                                "information_ratio": {"type": "number"},
                                "max_drawdown": {"type": "number"},
                            },
                        },
                    },
                },
            ),
            Template(
                template_id="strategy_backtest_v1",
                name="Strategy Backtest Report",
                category=TemplateCategory.STRATEGY_BACKTEST,
                format=TemplateFormat.JSON,
                schema={
                    "type": "object",
                    "required": ["strategy_name", "period", "metrics", "analysis"],
                    "properties": {
                        "strategy_name": {"type": "string"},
                        "period": {"type": "object"},
                        "metrics": {"type": "object"},
                        "analysis": {"type": "string"},
                    },
                },
            ),
            Template(
                template_id="experiment_log_v1",
                name="Experiment Log",
                category=TemplateCategory.EXPERIMENT_LOG,
                format=TemplateFormat.JSON,
                schema={
                    "type": "object",
                    "required": ["experiment_id", "hypothesis", "results"],
                    "properties": {
                        "experiment_id": {"type": "string"},
                        "hypothesis": {"type": "string"},
                        "methodology": {"type": "string"},
                        "results": {"type": "object"},
                        "conclusion": {"type": "string"},
                    },
                },
            ),
        ]

        for template in defaults:
            self.register(template)

    def register(self, template: Template) -> str:
        """Register a new output template."""
        self._templates[template.template_id] = template
        if template.category in self._category_index:
            self._category_index[template.category].append(template.template_id)
        logger.debug("Registered template: %s v%d", template.template_id, template.version)
        return template.template_id

    def get(self, template_id: str) -> Optional[Template]:
        """Get a template by ID."""
        template = self._templates.get(template_id)
        if template:
            template.usage_count += 1
        return template

    def list_by_category(self, category: TemplateCategory) -> list[Template]:
        """List templates in a category."""
        ids = self._category_index.get(category, [])
        return [self._templates[tid] for tid in ids if tid in self._templates]

    def list_by_format(self, format: TemplateFormat) -> list[Template]:
        """List templates by output format."""
        return [t for t in self._templates.values() if t.format == format]

    def validate(self, template_id: str, data: dict[str, Any]) -> list[str]:
        """Validate output data against a template schema."""
        template = self.get(template_id)
        if template is None:
            return [f"Template {template_id} not found"]

        errors: list[str] = []
        schema = template.schema

        # Check required fields
        for required_field in schema.get("required", []):
            if required_field not in data:
                errors.append(f"Missing required field: {required_field}")

        return errors

    @property
    def template_count(self) -> int:
        return len(self._templates)
