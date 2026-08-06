"""Experiment Metadata — structured metadata for research experiments.

Supports rich metadata including:
* Author/owner attribution
* Hypothesis description
* Methodology notes
* References and citations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ExperimentMetadata:
    """Structured metadata for describing research experiments.

    Captures the context, intent, and methodology of an experiment
    for discoverability and reproducibility.
    """

    title: str = ""
    description: str = ""
    hypothesis: str = ""
    methodology: str = ""
    author: Optional[str] = None
    owner: Optional[str] = None
    team: Optional[str] = None
    project: Optional[str] = None
    category: str = ""
    subcategory: str = ""
    priority: str = "medium"  # low, medium, high, critical
    references: List[str] = field(default_factory=list)
    citations: List[str] = field(default_factory=list)
    related_experiments: List[str] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "hypothesis": self.hypothesis,
            "methodology": self.methodology,
            "author": self.author,
            "owner": self.owner,
            "team": self.team,
            "project": self.project,
            "category": self.category,
            "subcategory": self.subcategory,
            "priority": self.priority,
            "references": self.references,
            "citations": self.citations,
            "related_experiments": self.related_experiments,
            "custom_fields": self.custom_fields,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperimentMetadata":
        return cls(
            title=data.get("title", ""),
            description=data.get("description", ""),
            hypothesis=data.get("hypothesis", ""),
            methodology=data.get("methodology", ""),
            author=data.get("author"),
            owner=data.get("owner"),
            team=data.get("team"),
            project=data.get("project"),
            category=data.get("category", ""),
            subcategory=data.get("subcategory", ""),
            priority=data.get("priority", "medium"),
            references=data.get("references", []),
            citations=data.get("citations", []),
            related_experiments=data.get("related_experiments", []),
            custom_fields=data.get("custom_fields", {}),
        )

    def __repr__(self) -> str:
        return f"ExperimentMetadata(title={self.title!r})"
