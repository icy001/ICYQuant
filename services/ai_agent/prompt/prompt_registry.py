"""
Prompt registry for template storage and discovery.

Manages the catalog of prompt templates with versioning,
categorization, and lookup capabilities.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from services.ai_agent.prompt.prompt_template import (
    PromptTemplate,
    TemplateCategory,
)

logger = logging.getLogger(__name__)


class PromptRegistry:
    """Registry for prompt templates.

    Provides storage, versioning, search, and discovery
    for all prompt templates in the platform.

    Usage:
        registry = PromptRegistry()
        registry.register(template)
        tpl = registry.get("research_query")
    """

    def __init__(self) -> None:
        self._templates: Dict[str, PromptTemplate] = {}  # template_id → template
        self._by_name: Dict[str, List[str]] = {}          # name → [template_ids]
        self._by_category: Dict[str, List[str]] = {}      # category → [template_ids]
        logger.info("PromptRegistry created")

    # ── Registration ──

    def register(self, template: PromptTemplate) -> PromptTemplate:
        """Register a prompt template.

        Args:
            template: The template to register.

        Returns:
            The registered template.
        """
        self._templates[template.template_id] = template

        # Name index
        self._by_name.setdefault(template.name, [])
        self._by_name[template.name].append(template.template_id)

        # Category index
        cat_key = template.category.value
        self._by_category.setdefault(cat_key, [])
        self._by_category[cat_key].append(template.template_id)

        logger.debug(f"Registered prompt template: {template.name} v{template.version}")
        return template

    def unregister(self, template_id: str) -> bool:
        """Remove a template from the registry."""
        template = self._templates.pop(template_id, None)
        if not template:
            return False

        # Clean up indexes
        if template.name in self._by_name:
            self._by_name[template.name] = [
                tid for tid in self._by_name[template.name] if tid != template_id
            ]
        cat_key = template.category.value
        if cat_key in self._by_category:
            self._by_category[cat_key] = [
                tid for tid in self._by_category[cat_key] if tid != template_id
            ]

        return True

    # ── Retrieval ──

    def get(self, template_id: str) -> Optional[PromptTemplate]:
        """Get a template by ID."""
        return self._templates.get(template_id)

    def get_latest_by_name(self, name: str) -> Optional[PromptTemplate]:
        """Get the latest version of a template by name."""
        ids = self._by_name.get(name, [])
        templates = [self._templates[tid] for tid in ids if tid in self._templates]
        if not templates:
            return None
        return max(templates, key=lambda t: t.version)

    def get_all_versions(self, name: str) -> List[PromptTemplate]:
        """Get all versions of a template by name."""
        ids = self._by_name.get(name, [])
        return sorted(
            [self._templates[tid] for tid in ids if tid in self._templates],
            key=lambda t: t.version,
        )

    def find_by_category(self, category: TemplateCategory) -> List[PromptTemplate]:
        """Find templates by category."""
        ids = self._by_category.get(category.value, [])
        return [self._templates[tid] for tid in ids if tid in self._templates]

    def find_by_tag(self, tag: str) -> List[PromptTemplate]:
        """Find templates by tag."""
        return [
            t for t in self._templates.values()
            if tag in t.tags
        ]

    def search(self, query: str, limit: int = 20) -> List[PromptTemplate]:
        """Search templates by name and description."""
        query_lower = query.lower()
        results = []
        for t in self._templates.values():
            score = 0
            if query_lower in t.name.lower():
                score += 3
            if query_lower in t.description.lower():
                score += 2
            if any(query_lower in tag.lower() for tag in t.tags):
                score += 1
            if score > 0:
                results.append((score, t))

        results.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in results[:limit]]

    def list_all(self) -> List[PromptTemplate]:
        """List all registered templates."""
        return list(self._templates.values())

    # ── Status ──

    @property
    def size(self) -> int:
        """Total registered templates."""
        return len(self._templates)

    def get_summary(self) -> Dict[str, Any]:
        """Get registry summary."""
        cat_counts = {
            cat: len(ids) for cat, ids in self._by_category.items()
        }
        return {
            "total_templates": self.size,
            "unique_names": len(self._by_name),
            "by_category": cat_counts,
        }
