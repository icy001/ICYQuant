"""
Prompt template with versioning and variable support.

Defines the structure and variables for prompt construction,
with versioning for change tracking and rollback.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ── Template Types ──


class TemplateCategory(str, Enum):
    """Prompt template categories."""

    SYSTEM = "system"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    PLANNING = "planning"
    REASONING = "reasoning"
    EXECUTION = "execution"
    CODING = "coding"
    CHAT = "chat"
    CUSTOM = "custom"


@dataclass
class PromptTemplate:
    """A versioned prompt template with variable placeholders.

    Variables are defined using {{ variable_name }} syntax.

    Usage:
        template = PromptTemplate(
            name="research_query",
            template="Analyze {{ symbol }} over {{ timeframe }} timeframe.",
            variables=["symbol", "timeframe"],
        )
    """

    template_id: str = field(default_factory=lambda: uuid4().hex)
    name: str = ""
    description: str = ""
    category: TemplateCategory = TemplateCategory.CUSTOM
    template: str = ""
    variables: List[str] = field(default_factory=list)
    default_values: Dict[str, str] = field(default_factory=dict)
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    author: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_variables(self) -> List[str]:
        """Extract variable names from template text.

        Scans for {{ variable_name }} patterns.
        """
        import re
        pattern = r"\{\{\s*(\w+)\s*\}\}"
        return re.findall(pattern, self.template)

    def validate_variables(self, values: Dict[str, str]) -> List[str]:
        """Check which required variables are missing.

        Args:
            values: Variable name → value mapping.

        Returns:
            List of missing variable names.
        """
        required = set(self.variables)
        provided = set(values.keys())
        return list(required - provided)

    def render(self, variables: Dict[str, str]) -> str:
        """Render template with variable substitution.

        Args:
            variables: Variable name → value mapping.

        Returns:
            Rendered template string.
        """
        result = self.template
        for var_name, var_value in variables.items():
            result = result.replace(f"{{{{ {var_name} }}}}", str(var_value))
            result = result.replace(f"{{{{{var_name}}}}}", str(var_value))
        return result

    def to_dict(self) -> Dict[str, Any]:
        """Convert template to dictionary."""
        return {
            "template_id": self.template_id,
            "name": self.name,
            "category": self.category.value,
            "version": self.version,
            "variable_count": len(self.variables),
            "template_length": len(self.template),
        }

    def new_version(self, template: str) -> "PromptTemplate":
        """Create a new version of this template."""
        return PromptTemplate(
            name=self.name,
            description=self.description,
            category=self.category,
            template=template,
            variables=self.get_variables(),
            default_values=self.default_values,
            version=self.version + 1,
            author=self.author,
            tags=self.tags,
        )
