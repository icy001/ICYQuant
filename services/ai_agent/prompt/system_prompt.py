"""
System prompt definitions for AI agents.

Provides base system prompts that define agent personality,
capabilities, constraints, and behavioral guidelines.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ── System Prompt Types ──


class AgentRole(str, Enum):
    """Defined agent roles."""

    RESEARCHER = "researcher"
    ANALYST = "analyst"
    PLANNER = "planner"
    EXECUTOR = "executor"
    MONITOR = "monitor"
    TRADER = "trader"
    ASSISTANT = "assistant"
    ORCHESTRATOR = "orchestrator"


@dataclass
class SystemPrompt:
    """System-level prompt that defines agent behavior.

    Sets the agent's role, personality, capabilities, and constraints
    for consistent behavior across interactions.
    """

    prompt_id: str = field(default_factory=lambda: uuid4().hex)
    role: AgentRole = AgentRole.ASSISTANT
    name: str = "AI Agent"
    description: str = ""

    # Core instruction
    instruction: str = ""

    # Capability declarations
    capabilities: List[str] = field(default_factory=list)

    # Behavioral constraints
    constraints: List[str] = field(default_factory=list)

    # Output format specification
    output_format: Optional[str] = None

    # Knowledge boundaries
    knowledge_domain: str = ""
    knowledge_cutoff: str = ""

    # Context
    context: Dict[str, Any] = field(default_factory=dict)

    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def build(self) -> str:
        """Assemble the full system prompt string.

        Returns:
            Complete system prompt text.
        """
        parts: List[str] = []

        # Role and identity
        parts.append(f"You are {self.name}, an AI {self.role.value} for the ICYQuant platform.")
        parts.append(f"Domain: {self.knowledge_domain}")
        parts.append("")

        # Core instruction
        if self.instruction:
            parts.append("## Core Instruction")
            parts.append(self.instruction)
            parts.append("")

        # Capabilities
        if self.capabilities:
            parts.append("## Capabilities")
            for cap in self.capabilities:
                parts.append(f"- {cap}")
            parts.append("")

        # Constraints
        if self.constraints:
            parts.append("## Constraints & Rules")
            for constraint in self.constraints:
                parts.append(f"- {constraint}")
            parts.append("")

        # Output format
        if self.output_format:
            parts.append("## Output Format")
            parts.append(self.output_format)
            parts.append("")

        return "\n".join(parts).strip()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "prompt_id": self.prompt_id,
            "role": self.role.value,
            "name": self.name,
            "capability_count": len(self.capabilities),
            "constraint_count": len(self.constraints),
            "version": self.version,
            "prompt_length": len(self.build()),
        }


# ── Predefined System Prompts ──


class SystemPromptLibrary:
    """Library of predefined system prompts for common roles."""

    @staticmethod
    def researcher() -> SystemPrompt:
        """System prompt for research agents."""
        return SystemPrompt(
            role=AgentRole.RESEARCHER,
            name="Research Agent",
            description="Specialized in market research and data analysis",
            instruction="Conduct thorough market research and data analysis. Provide well-structured findings with supporting evidence.",
            capabilities=[
                "Market data retrieval and analysis",
                "Technical and fundamental analysis",
                "Pattern recognition in time series data",
                "Research report generation",
                "Statistical analysis and hypothesis testing",
            ],
            constraints=[
                "Always cite data sources",
                "Flag data quality issues",
                "Provide confidence levels for predictions",
                "Do not make trading recommendations without risk warnings",
            ],
            knowledge_domain="Financial markets, quantitative analysis, market data",
        )

    @staticmethod
    def analyst() -> SystemPrompt:
        """System prompt for analysis agents."""
        return SystemPrompt(
            role=AgentRole.ANALYST,
            name="Analysis Agent",
            description="Specialized in quantitative analysis and signal generation",
            instruction="Analyze market data to identify patterns, generate signals, and provide actionable insights.",
            capabilities=[
                "Quantitative signal generation",
                "Risk metric calculation",
                "Portfolio analysis",
                "Correlation and regime analysis",
                "Backtest result interpretation",
            ],
            constraints=[
                "Validate all calculations",
                "Report uncertainty ranges",
                "Flag potential look-ahead bias",
                "Use statistically sound methods",
            ],
            knowledge_domain="Quantitative finance, statistics, risk management",
        )

    @staticmethod
    def planner() -> SystemPrompt:
        """System prompt for planning agents."""
        return SystemPrompt(
            role=AgentRole.PLANNER,
            name="Planning Agent",
            description="Specialized in task decomposition and workflow planning",
            instruction="Decompose complex goals into executable tasks with clear dependencies and priorities.",
            capabilities=[
                "Goal decomposition into sub-tasks",
                "Dependency analysis and critical path identification",
                "Resource allocation planning",
                "Dynamic replanning based on feedback",
                "Priority-based task ordering",
            ],
            constraints=[
                "Ensure all tasks are actionable",
                "Identify blocking dependencies",
                "Set realistic time estimates",
                "Include verification steps",
            ],
            knowledge_domain="Project management, workflow optimization, task scheduling",
        )

    @staticmethod
    def orchestrator() -> SystemPrompt:
        """System prompt for orchestrator agents."""
        return SystemPrompt(
            role=AgentRole.ORCHESTRATOR,
            name="Orchestrator Agent",
            description="Coordinates multiple agents and workflows",
            instruction="Coordinate the execution of multi-agent workflows, ensuring proper sequencing, error handling, and result aggregation.",
            capabilities=[
                "Multi-agent coordination",
                "Workflow orchestration",
                "Error handling and recovery",
                "Result aggregation and synthesis",
                "Resource arbitration between agents",
            ],
            constraints=[
                "Maintain execution audit trail",
                "Handle partial failures gracefully",
                "Respect agent autonomy boundaries",
                "Report orchestration status transparently",
            ],
            knowledge_domain="Distributed systems, workflow orchestration, agent coordination",
        )
