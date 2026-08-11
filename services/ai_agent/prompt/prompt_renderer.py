"""
Prompt renderer for variable substitution and environment overrides.

Renders prompt templates with contextual variables, applying
environment-specific transformations and content assembly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.ai_agent.prompt.prompt_template import PromptTemplate

logger = logging.getLogger(__name__)


# ── Renderer Types ──


@dataclass
class RenderContext:
    """Context for template rendering."""

    variables: Dict[str, str] = field(default_factory=dict)
    environment: str = "default"
    locale: str = "en"
    include_metadata: bool = True
    max_length: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RenderedPrompt:
    """Fully rendered prompt ready for LLM consumption."""

    prompt_id: str = ""
    content: str = ""
    template_id: str = ""
    template_name: str = ""
    template_version: int = 0
    character_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "prompt_id": self.prompt_id,
            "template_id": self.template_id,
            "template_name": self.template_name,
            "template_version": self.template_version,
            "character_count": self.character_count,
            "content_preview": self.content[:200],
        }


# ── Prompt Renderer ──


class PromptRenderer:
    """Renders prompt templates into final prompt strings.

    Handles variable substitution, environment-specific overrides,
    and content assembly for LLM consumption.

    Usage:
        renderer = PromptRenderer()
        rendered = renderer.render(
            template=template,
            context=RenderContext(variables={"symbol": "BTC/USDT"}),
        )
    """

    def __init__(self) -> None:
        self._render_count: int = 0
        logger.info("PromptRenderer created")

    # ── Rendering ──

    def render(
        self,
        template: PromptTemplate,
        context: Optional[RenderContext] = None,
    ) -> RenderedPrompt:
        """Render a template into a final prompt.

        Args:
            template: The prompt template to render.
            context: Rendering context with variables and overrides.

        Returns:
            Fully rendered prompt.

        Raises:
            ValueError: If required variables are missing.
        """
        ctx = context or RenderContext()
        self._render_count += 1

        # Validate required variables
        missing = template.validate_variables(ctx.variables)
        if missing:
            raise ValueError(
                f"Missing required variables for template [{template.name}]: {missing}"
            )

        # Apply default values for unset optional variables
        variables = dict(template.default_values)
        variables.update(ctx.variables)

        # Render template
        content = template.render(variables)

        # Apply environment overrides
        content = self._apply_environment_overrides(content, ctx)

        # Truncate if needed
        if ctx.max_length and len(content) > ctx.max_length:
            logger.warning(
                f"Prompt exceeds max length ({len(content)} > {ctx.max_length}), truncating"
            )
            content = content[: ctx.max_length]

        rendered = RenderedPrompt(
            prompt_id=template.template_id,
            content=content,
            template_id=template.template_id,
            template_name=template.name,
            template_version=template.version,
            character_count=len(content),
            metadata={
                "variables_used": list(variables.keys()),
                "environment": ctx.environment,
                "locale": ctx.locale,
                **ctx.metadata,
            },
        )

        logger.debug(
            f"Rendered prompt [{template.name}]: {len(content)} chars"
        )
        return rendered

    def render_multiple(
        self,
        templates: List[PromptTemplate],
        context: Optional[RenderContext] = None,
    ) -> List[RenderedPrompt]:
        """Render multiple templates."""
        return [self.render(t, context) for t in templates]

    # ── Environment Overrides ──

    def _apply_environment_overrides(
        self,
        content: str,
        context: RenderContext,
    ) -> str:
        """Apply environment-specific modifications to content.

        Args:
            content: Rendered content.
            context: Render context with environment info.

        Returns:
            Modified content.
        """
        if context.environment == "production":
            # Strip debug information
            pass
        elif context.environment == "development":
            # Add development markers
            pass

        return content

    # ── Status ──

    @property
    def total_renders(self) -> int:
        """Total renders performed."""
        return self._render_count
