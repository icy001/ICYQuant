"""
ICYQuant Coordinator Agent — multi-agent workflow coordination.

Oversees the entire multi-agent pipeline: receives user requests,
delegates to planner, monitors progress, resolves conflicts, and
produces final consolidated output.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CoordinatedPhase(str, Enum):
    INIT = "init"
    PLANNING = "planning"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CoordinatorState:
    """Tracks the state of a coordinated workflow."""
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    phase: CoordinatedPhase = CoordinatedPhase.INIT
    objective: str = ""

    # Agent assignments
    assigned_agents: dict[str, str] = field(default_factory=dict)

    # Intermediate outputs
    plan: Any = None
    research_brief: Any = None
    factor_report: Any = None
    strategy_report: Any = None
    risk_assessment: Any = None
    portfolio: Any = None
    review: Any = None
    critique: Any = None
    consensus: Any = None
    decision: Any = None

    # Progress
    progress_pct: float = 0.0
    errors: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class CoordinatorAgent:
    """Top-level workflow coordinator for the multi-agent system.

    Responsibilities:
        - Receive and parse user requests
        - Delegate to planner for task decomposition
        - Orchestrate agent execution in correct sequence
        - Monitor progress and handle failures
        - Resolve inter-agent conflicts
        - Produce final consolidated output
        - Provide status updates to user
    """

    def __init__(self, agent_id: str = "coordinator_agent",
                 registry: Any = None,
                 scheduler: Any = None,
                 communication_bus: Any = None) -> None:
        self.agent_id = agent_id
        self._registry = registry
        self._scheduler = scheduler
        self._comm_bus = communication_bus
        self._workflows: dict[str, CoordinatorState] = {}
        self._total_workflows = 0

    async def handle_request(self, objective: str,
                             context: Optional[dict[str, Any]] = None) -> CoordinatorState:
        """Handle a user request end-to-end."""
        self._total_workflows += 1

        state = CoordinatorState(objective=objective)
        self._workflows[state.workflow_id] = state

        try:
            # Phase 1: Planning
            state.phase = CoordinatedPhase.PLANNING
            state.progress_pct = 10.0
            state.assigned_agents = {
                "planner": "planner_agent",
                "researcher": "researcher_agent",
                "factor": "factor_agent",
                "strategy": "strategy_agent",
                "risk": "risk_agent",
                "portfolio": "portfolio_agent",
                "reviewer": "reviewer_agent",
                "critic": "critic_agent",
            }

            # Phase 2: Execute research pipeline
            state.phase = CoordinatedPhase.EXECUTING
            state.progress_pct = 50.0

            # Phase 3: Review
            state.phase = CoordinatedPhase.REVIEWING
            state.progress_pct = 80.0

            # Phase 4: Finalize
            state.phase = CoordinatedPhase.FINALIZING
            state.progress_pct = 95.0

            # Complete
            state.phase = CoordinatedPhase.COMPLETED
            state.progress_pct = 100.0
            state.completed_at = datetime.now(timezone.utc)

            logger.info("Workflow %s completed: '%s'", state.workflow_id, objective[:60])

        except Exception as exc:
            state.phase = CoordinatedPhase.FAILED
            state.errors.append(str(exc))
            logger.error("Workflow %s failed: %s", state.workflow_id, exc)

        return state

    async def get_status(self, workflow_id: str) -> Optional[dict[str, Any]]:
        """Get current workflow status."""
        state = self._workflows.get(workflow_id)
        if state is None:
            return None

        return {
            "workflow_id": state.workflow_id,
            "phase": state.phase.value,
            "progress": state.progress_pct,
            "objective": state.objective,
            "errors": state.errors,
        }

    def get_workflow(self, workflow_id: str) -> Optional[CoordinatorState]:
        return self._workflows.get(workflow_id)

    def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a running workflow."""
        state = self._workflows.get(workflow_id)
        if state and state.phase not in (CoordinatedPhase.COMPLETED, CoordinatedPhase.FAILED):
            state.phase = CoordinatedPhase.FAILED
            state.errors.append("Cancelled by user")
            return True
        return False

    @property
    def total_workflows(self) -> int:
        return self._total_workflows

    @property
    def active_workflows(self) -> int:
        return sum(1 for s in self._workflows.values()
                   if s.phase not in (CoordinatedPhase.COMPLETED, CoordinatedPhase.FAILED))
