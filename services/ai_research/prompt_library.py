"""
ICYQuant Prompt Library — curated collection of research prompts and templates.

Manages prompt creation, versioning, categorization, and retrieval for
consistent, high-quality LLM interactions across the research platform.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PromptCategory(str, Enum):
    RESEARCH_QUESTION = "research_question"
    HYPOTHESIS_GENERATION = "hypothesis_generation"
    EVIDENCE_ANALYSIS = "evidence_analysis"
    REPORT_WRITING = "report_writing"
    DATA_ANALYSIS = "data_analysis"
    FACTOR_RESEARCH = "factor_research"
    STRATEGY_EVALUATION = "strategy_evaluation"
    RISK_ASSESSMENT = "risk_assessment"
    GENERAL = "general"


@dataclass
class Prompt:
    """A reusable prompt template."""
    prompt_id: str
    name: str
    category: PromptCategory
    template: str
    version: int = 1
    description: str = ""
    variables: list[str] = field(default_factory=list)
    examples: list[dict[str, str]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    usage_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class PromptLibrary:
    """Curated collection of research prompt templates.

    Responsibilities:
        - Prompt creation and versioning
        - Category-based organization
        - Variable interpolation
        - Usage tracking
        - Quality consistency across research workflows
    """

    def __init__(self) -> None:
        self._prompts: dict[str, Prompt] = {}
        self._category_index: dict[PromptCategory, list[str]] = {
            c: [] for c in PromptCategory
        }
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register built-in research prompts."""
        defaults = [
            Prompt(
                prompt_id="research_question_analysis",
                name="Research Question Analysis",
                category=PromptCategory.RESEARCH_QUESTION,
                template="""Analyze the following research question in the context of quantitative finance:

Question: {{question}}

Context: {{context}}

Please provide:
1. Key concepts involved
2. Relevant quantitative methods
3. Potential data requirements
4. Expected challenges""",
                variables=["question", "context"],
            ),
            Prompt(
                prompt_id="hypothesis_generation",
                name="Hypothesis Generation",
                category=PromptCategory.HYPOTHESIS_GENERATION,
                template="""Based on the following research context, generate testable hypotheses:

Research Question: {{question}}
Available Evidence: {{evidence}}
Domain Knowledge: {{knowledge}}

Generate 3-5 specific, testable hypotheses with:
- Clear null and alternative formulations
- Required data to test
- Expected effect direction""",
                variables=["question", "evidence", "knowledge"],
            ),
            Prompt(
                prompt_id="evidence_evaluation",
                name="Evidence Evaluation",
                category=PromptCategory.EVIDENCE_ANALYSIS,
                template="""Evaluate the following evidence for the research hypothesis:

Hypothesis: {{hypothesis}}
Evidence: {{evidence}}

For each piece of evidence, assess:
1. Relevance (1-10)
2. Strength (1-10)
3. Direction (supports / contradicts / neutral)
4. Limitations""",
                variables=["hypothesis", "evidence"],
            ),
            Prompt(
                prompt_id="research_report_generation",
                name="Research Report Generation",
                category=PromptCategory.REPORT_WRITING,
                template="""Generate a comprehensive research report:

Research Question: {{question}}
Hypotheses: {{hypotheses}}
Evidence Summary: {{evidence_summary}}
Conclusions: {{conclusions}}

Report structure:
1. Executive Summary
2. Research Question & Context
3. Methodology
4. Findings & Evidence
5. Risk & Limitations
6. Conclusions & Recommendations""",
                variables=["question", "hypotheses", "evidence_summary", "conclusions"],
            ),
            Prompt(
                prompt_id="factor_research_analysis",
                name="Factor Research Analysis",
                category=PromptCategory.FACTOR_RESEARCH,
                template="""Analyze the following factor research context:

Factor: {{factor}}
Market: {{market}}
Period: {{period}}
Performance Data: {{data}}

Provide:
1. Factor behavior analysis
2. Regime dependency assessment
3. Correlation with known factors
4. Implementation considerations""",
                variables=["factor", "market", "period", "data"],
            ),
        ]

        for prompt in defaults:
            self.register(prompt)

    def register(self, prompt: Prompt) -> str:
        """Register a new prompt template."""
        self._prompts[prompt.prompt_id] = prompt
        if prompt.category in self._category_index:
            self._category_index[prompt.category].append(prompt.prompt_id)
        logger.debug("Registered prompt: %s v%d", prompt.prompt_id, prompt.version)
        return prompt.prompt_id

    def get(self, prompt_id: str) -> Optional[Prompt]:
        """Get a prompt by ID."""
        prompt = self._prompts.get(prompt_id)
        if prompt:
            prompt.usage_count += 1
        return prompt

    def render(self, prompt_id: str, variables: dict[str, str]) -> Optional[str]:
        """Render a prompt with variable interpolation."""
        prompt = self.get(prompt_id)
        if prompt is None:
            logger.warning("Prompt %s not found", prompt_id)
            return None

        result = prompt.template
        for var in prompt.variables:
            placeholder = f"{{{{{var}}}}}"
            value = variables.get(var, f"[{var}]")
            result = result.replace(placeholder, value)

        return result

    def list_by_category(self, category: PromptCategory) -> list[Prompt]:
        """List all prompts in a category."""
        ids = self._category_index.get(category, [])
        return [self._prompts[pid] for pid in ids if pid in self._prompts]

    def search(self, query: str, limit: int = 10) -> list[Prompt]:
        """Search prompts by name or description."""
        query_lower = query.lower()
        results = [
            p for p in self._prompts.values()
            if query_lower in p.name.lower() or query_lower in p.description.lower()
        ]
        return results[:limit]

    @property
    def prompt_count(self) -> int:
        return len(self._prompts)
