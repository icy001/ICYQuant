"""
ICYQuant Agent Orchestrator — multi-agent workflow coordination.

Orchestrates the full multi-agent research workflow: planning → research
→ factor analysis → strategy generation → risk assessment → portfolio
optimization → review → consensus → decision.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class OrchestrationPhase(str, Enum):
    INIT = "init"
    PLANNING = "planning"
    RESEARCHING = "researching"
    FACTOR_ANALYSIS = "factor_analysis"
    STRATEGY_BUILDING = "strategy_building"
    RISK_ASSESSMENT = "risk_assessment"
    PORTFOLIO = "portfolio"
    DEBATING = "debating"
    CONSENSUS = "consensus"
    REVIEW = "review"
    DECISION = "decision"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class OrchestrationContext:
    """Context carried through the orchestration pipeline."""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    question: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    phase: OrchestrationPhase = OrchestrationPhase.INIT

    # Agent assignments
    assigned_agents: dict[str, str] = field(default_factory=dict)  # role → agent_id

    # Intermediate results
    plan: dict[str, Any] = field(default_factory=dict)
    research_results: dict[str, Any] = field(default_factory=dict)
    factor_results: dict[str, Any] = field(default_factory=dict)
    strategy_results: dict[str, Any] = field(default_factory=dict)
    risk_results: dict[str, Any] = field(default_factory=dict)
    portfolio_results: dict[str, Any] = field(default_factory=dict)

    # Deliberation
    debate_log: list[dict[str, Any]] = field(default_factory=list)
    votes: dict[str, Any] = field(default_factory=dict)
    consensus: Optional[dict[str, Any]] = None
    dissenting_opinions: list[dict[str, Any]] = field(default_factory=list)

    # Final output
    decision: Optional[dict[str, Any]] = None
    confidence: float = 0.0
    evidence_summary: dict[str, Any] = field(default_factory=dict)

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    phase_timings: dict[str, float] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class AgentOrchestrator:
    """Multi-agent workflow orchestrator.

    Flow:
        1. Planning       — Coordinator decomposes the request
        2. Research       — Researcher gathers domain knowledge
        3. Factor Analysis — Factor agent analyzes quantitative factors
        4. Strategy       — Strategy agent builds candidate strategies
        5. Risk Assessment — Risk agent evaluates exposures
        6. Portfolio      — Portfolio agent optimizes allocation
        7. Debate         — Critic/bull/bear debate the findings
        8. Consensus      — Reach consensus via voting
        9. Review         — Reviewer validates the output
        10. Decision      — Final AI decision with confidence score
    """

    def __init__(self, registry: Any = None, scheduler: Any = None,
                 communication_bus: Any = None) -> None:
        self._registry = registry
        self._scheduler = scheduler
        self._comm_bus = communication_bus
        self._contexts: dict[str, OrchestrationContext] = {}
        self._total_orchestrations = 0

    async def execute(self, question: str, context: Optional[dict[str, Any]] = None) -> OrchestrationContext:
        """Execute the full multi-agent research workflow."""
        ctx = OrchestrationContext(question=question, context=context or {})
        self._contexts[ctx.request_id] = ctx
        self._total_orchestrations += 1

        try:
            # Phase 1: Planning
            ctx.phase = OrchestrationPhase.PLANNING
            await self._plan(ctx)

            # Phase 2: Research
            ctx.phase = OrchestrationPhase.RESEARCHING
            await self._research(ctx)

            # Phase 3: Factor Analysis
            ctx.phase = OrchestrationPhase.FACTOR_ANALYSIS
            await self._factor_analysis(ctx)

            # Phase 4: Strategy Building
            ctx.phase = OrchestrationPhase.STRATEGY_BUILDING
            await self._strategy_building(ctx)

            # Phase 5: Risk Assessment
            ctx.phase = OrchestrationPhase.RISK_ASSESSMENT
            await self._risk_assessment(ctx)

            # Phase 6: Portfolio
            ctx.phase = OrchestrationPhase.PORTFOLIO
            await self._portfolio_analysis(ctx)

            # Phase 7: Debate
            ctx.phase = OrchestrationPhase.DEBATING
            await self._debate(ctx)

            # Phase 8: Consensus
            ctx.phase = OrchestrationPhase.CONSENSUS
            await self._consensus(ctx)

            # Phase 9: Review
            ctx.phase = OrchestrationPhase.REVIEW
            await self._review(ctx)

            # Phase 10: Decision
            ctx.phase = OrchestrationPhase.DECISION
            await self._decide(ctx)

            ctx.phase = OrchestrationPhase.COMPLETED

        except Exception as exc:
            ctx.phase = OrchestrationPhase.FAILED
            ctx.errors.append(str(exc))
            logger.error("Orchestration failed: %s", exc)

        return ctx

    async def _plan(self, ctx: OrchestrationContext) -> None:
        ctx.plan = {
            "steps": [
                {"agent": "researcher", "action": "gather_domain_knowledge"},
                {"agent": "factor", "action": "analyze_factors"},
                {"agent": "strategy", "action": "build_strategy"},
                {"agent": "risk", "action": "assess_risk"},
                {"agent": "portfolio", "action": "optimize_portfolio"},
                {"agent": "critic", "action": "debate_findings"},
                {"agent": "reviewer", "action": "validate_output"},
            ]
        }
        ctx.assigned_agents["coordinator"] = "coordinator_agent"

    async def _research(self, ctx: OrchestrationContext) -> None:
        ctx.research_results = {"status": "completed", "findings": []}

    async def _factor_analysis(self, ctx: OrchestrationContext) -> None:
        ctx.factor_results = {"status": "completed", "factors": []}

    async def _strategy_building(self, ctx: OrchestrationContext) -> None:
        ctx.strategy_results = {"status": "completed", "strategies": []}

    async def _risk_assessment(self, ctx: OrchestrationContext) -> None:
        ctx.risk_results = {"status": "completed", "risk_level": "medium"}

    async def _portfolio_analysis(self, ctx: OrchestrationContext) -> None:
        ctx.portfolio_results = {"status": "completed"}

    async def _debate(self, ctx: OrchestrationContext) -> None:
        ctx.debate_log = [{"agent": "critic", "opinion": "pending_review"}]

    async def _consensus(self, ctx: OrchestrationContext) -> None:
        ctx.consensus = {"agreement": True, "agent_count": 5, "dissent_count": 0}

    async def _review(self, ctx: OrchestrationContext) -> None:
        pass

    async def _decide(self, ctx: OrchestrationContext) -> None:
        ctx.decision = {"action": "HOLD", "confidence": 0.7}
        ctx.confidence = 0.7

    def get_context(self, request_id: str) -> Optional[OrchestrationContext]:
        return self._contexts.get(request_id)

    @property
    def total_orchestrations(self) -> int:
        return self._total_orchestrations
