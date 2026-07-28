"""Research Agent data model for the Agentic Research Platform."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ResearchAgent:
    """An autonomous research agent with a specific role and capabilities.

    Attributes:
        id: Unique identifier.
        role: Agent role (e.g. "financial", "industry", "valuation").
        capability: List of analysis capabilities.
    """

    id: str
    role: str
    capability: list[str] = field(default_factory=list)
