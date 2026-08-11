"""
Prompt manager orchestrating prompt lifecycle.

Unified prompt management:
    Template → Render → Validation → Prompt → LLM

Coordinates template registration, rendering, validation,
and delivery for LLM interactions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from services.ai_agent.prompt.prompt_template import (
    PromptTemplate,
    TemplateCategory,
)
from services.ai_agent.prompt.prompt_registry import PromptRegistry
from services.ai_agent.prompt.prompt_renderer import (
    PromptRenderer,
    RenderContext,
    RenderedPrompt,
)
from services.ai_agent.prompt.prompt_validator import PromptValidator

logger = logging.getLogger(__name__)


# ── Re-export for convenience ──
__all__ = ["PromptManager", "RenderContext"]


# ── Prompt Manager ──


class PromptManager:
    """Orchestrates the full prompt lifecycle.

    Coordinates template management, rendering, validation,
    and delivery for all LLM prompt needs.

    Usage:
        mgr = PromptManager()
        mgr.register_template(template)
        prompt = mgr.build_prompt("research_query", {"symbol": "BTC"})
    """

    def __init__(self) -> None:
        self.registry = PromptRegistry()
        self.renderer = PromptRenderer()
        self.validator = PromptValidator()
        self._build_count: int = 0
        logger.info("PromptManager created")

    # ── Template Management ──

    def register_template(self, template: PromptTemplate) -> PromptTemplate:
        """Register a prompt template.

        Args:
            template: The template to register.

        Returns:
            The registered template.
        """
        return self.registry.register(template)

    def get_template(self, name: str, version: Optional[int] = None) -> Optional[PromptTemplate]:
        """Get a template by name, optionally specifying version.

        Args:
            name: Template name.
            version: Specific version; latest if None.

        Returns:
            The template or None.
        """
        if version:
            versions = self.registry.get_all_versions(name)
            for t in versions:
                if t.version == version:
                    return t
            return None
        return self.registry.get_latest_by_name(name)

    def list_templates(self, category: Optional[TemplateCategory] = None) -> List[Dict[str, Any]]:
        """List templates, optionally filtered by category."""
        if category:
            templates = self.registry.find_by_category(category)
        else:
            templates = self.registry.list_all()
        return [t.to_dict() for t in templates]

    # ── Prompt Building ──

    def build_prompt(
        self,
        template_name: str,
        variables: Optional[Dict[str, str]] = None,
        environment: str = "default",
        max_length: Optional[int] = None,
    ) -> RenderedPrompt:
        """Build a prompt from a named template with variables.

        This is the primary interface for prompt construction.

        Args:
            template_name: Name of the registered template.
            variables: Variable values for substitution.
            environment: Environment context (default, production, development).
            max_length: Optional maximum prompt length.

        Returns:
            Fully rendered prompt.

        Raises:
            ValueError: If template not found or validation fails.
        """
        template = self.get_template(template_name)
        if not template:
            raise ValueError(f"Template not found: {template_name}")

        ctx = RenderContext(
            variables=variables or {},
            environment=environment,
            max_length=max_length,
        )

        rendered = self.renderer.render(template, ctx)
        self._build_count += 1

        return rendered

    def build_from_template(
        self,
        template: PromptTemplate,
        variables: Optional[Dict[str, str]] = None,
        environment: str = "default",
    ) -> RenderedPrompt:
        """Build a prompt from a template object.

        Args:
            template: The template to render.
            variables: Variable values.
            environment: Environment context.

        Returns:
            Fully rendered prompt.
        """
        ctx = RenderContext(
            variables=variables or {},
            environment=environment,
        )
        rendered = self.renderer.render(template, ctx)
        self._build_count += 1
        return rendered

    # ── Validation ──

    def validate_prompt(self, content: str, max_length: int = 8000) -> Dict[str, Any]:
        """Validate a prompt string.

        Args:
            content: The prompt content to validate.
            max_length: Maximum allowed length.

        Returns:
            Validation result dict.
        """
        return self.validator.validate(content, max_length=max_length)

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get prompt manager summary."""
        return {
            "registry": self.registry.get_summary(),
            "total_builds": self._build_count,
            "total_renders": self.renderer.total_renders,
        }
