"""Agent Coordinator - orchestrates multi-agent collaboration workflow."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict

from .message import AgentIdentity, AgentRole, AgentMessage, MessagePriority, MessageType
from .communication import AgentCommunicationBus
from .delegation import TaskDelegationEngine, Task, TaskDomain, TaskStatus, DelegationPlan


class CoordinationMode(Enum):
    """Mode of agent coordination."""
    SEQUENTIAL = "SEQUENTIAL"
    PARALLEL = "PARALLEL"
    HIERARCHICAL = "HIERARCHICAL"
    CONSENSUS = "CONSENSUS"
    DEBATE = "DEBATE"


class WorkflowPhase(Enum):
    """Phases in a coordination workflow."""
    INIT = "INIT"
    RESEARCH = "RESEARCH"
    ANALYSIS = "ANALYSIS"
    DECISION = "DECISION"
    EXECUTION = "EXECUTION"
    REVIEW = "REVIEW"
    LEARNING = "LEARNING"


@dataclass
class CoordinationContext:
    """Context for a coordination session."""
    session_id: str
    mode: CoordinationMode
    topic: str
    participants: List[AgentIdentity] = field(default_factory=list)
    phases: List[WorkflowPhase] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)


class AgentCoordinator:
    """Central coordinator for multi-agent collaboration.

    Responsibilities:
    - Manage agent lifecycles
    - Define collaboration workflows
    - Orchestrate task execution order
    - Manage shared state between agents
    - Enforce coordination protocols
    - Handle resource allocation

    Organization Structure:
    ```
                    CIO Agent
                       |
        ┌──────────────┼──────────────┐
        |              |              |
    Research      Strategy       Risk
        |              |              |
    Learning     Portfolio     Execution
    ```
    """

    def __init__(self, bus: AgentCommunicationBus, delegation: TaskDelegationEngine):
        self.bus = bus
        self.delegation = delegation
        self._agents: Dict[str, AgentIdentity] = {}
        self._sessions: Dict[str, CoordinationContext] = {}
        self._workflows: Dict[str, List[WorkflowPhase]] = {}
        self._agent_states: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._session_counter = 0

        # Default investment committee workflow
        self.register_workflow(
            "investment_committee",
            [
                WorkflowPhase.RESEARCH,
                WorkflowPhase.ANALYSIS,
                WorkflowPhase.DECISION,
                WorkflowPhase.EXECUTION,
                WorkflowPhase.REVIEW,
            ],
        )

    def register_agent(self, agent: AgentIdentity):
        """Register an agent with the coordinator."""
        self._agents[agent.agent_id] = agent
        self.bus.register_agent(agent)
        self.delegation.register_agent(agent)

    def register_workflow(self, name: str, phases: List[WorkflowPhase]):
        """Register a named workflow template."""
        self._workflows[name] = phases

    def coordinate(self, agents: List[AgentIdentity]) -> Dict[str, Any]:
        """Coordinate a set of agents.

        Args:
            agents: List of agents to coordinate.

        Returns:
            Dict with coordination result.
        """
        for agent in agents:
            self.register_agent(agent)

        return {
            "agents": [a.to_dict() for a in self._agents.values()],
            "count": len(self._agents),
            "roles": list(set(a.role.value for a in self._agents.values())),
        }

    def start_session(self, topic: str, mode: CoordinationMode,
                      participants: List[AgentIdentity],
                      workflow_name: str = "investment_committee") -> CoordinationContext:
        """Start a new coordination session.

        This is the main entry point for multi-agent collaboration.
        """
        self._session_counter += 1
        session = CoordinationContext(
            session_id=f"session_{self._session_counter}",
            mode=mode,
            topic=topic,
            participants=participants,
            phases=self._workflows.get(workflow_name, []),
        )
        self._sessions[session.session_id] = session

        # Notify all participants
        for agent in participants:
            self.bus.notify(
                sender=participants[0],
                task=f"Session started: {topic}",
                data={"session_id": session.session_id, "mode": mode.value},
                receivers=[agent],
            )

        return session

    def run_investment_committee(self, topic: str, market_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run a full investment committee workflow.

        Simulates an institutional investment committee:
        Research → Analysis → Decision → Execution → Review

        This is the core AI Organization pattern.
        """
        # Find agents by role
        cio_agents = [a for a in self._agents.values() if a.role == AgentRole.CIO]
        research_agents = [a for a in self._agents.values() if a.role == AgentRole.RESEARCH]
        strategy_agents = [a for a in self._agents.values() if a.role == AgentRole.STRATEGY]
        risk_agents = [a for a in self._agents.values() if a.role == AgentRole.RISK]
        portfolio_agents = [a for a in self._agents.values() if a.role == AgentRole.PORTFOLIO]
        execution_agents = [a for a in self._agents.values() if a.role == AgentRole.EXECUTION]
        learning_agents = [a for a in self._agents.values() if a.role == AgentRole.LEARNING]

        all_participants = (
            cio_agents + research_agents + strategy_agents +
            risk_agents + portfolio_agents + execution_agents + learning_agents
        )

        session = self.start_session(
            topic=topic,
            mode=CoordinationMode.SEQUENTIAL,
            participants=all_participants,
        )

        committee_results = {
            "topic": topic,
            "session_id": session.session_id,
            "phases": {},
        }

        # Phase 1: Research
        if research_agents:
            committee_results["phases"]["research"] = self._execute_phase(
                WorkflowPhase.RESEARCH,
                research_agents,
                f"Research: {topic}",
                market_data or {},
            )

        # Phase 2: Analysis (Strategy + Risk)
        analysis_results = {}
        if strategy_agents:
            analysis_results["strategy"] = self._execute_phase(
                WorkflowPhase.ANALYSIS,
                strategy_agents,
                f"Strategy Analysis: {topic}",
                market_data or {},
            )
        if risk_agents:
            analysis_results["risk"] = self._execute_phase(
                WorkflowPhase.ANALYSIS,
                risk_agents,
                f"Risk Analysis: {topic}",
                market_data or {},
            )
        committee_results["phases"]["analysis"] = analysis_results

        # Phase 3: Decision (Portfolio + CIO)
        if portfolio_agents:
            committee_results["phases"]["decision"] = self._execute_phase(
                WorkflowPhase.DECISION,
                portfolio_agents,
                f"Portfolio Decision: {topic}",
                committee_results,
            )

        # Phase 4: Execution
        if execution_agents:
            committee_results["phases"]["execution"] = self._execute_phase(
                WorkflowPhase.EXECUTION,
                execution_agents,
                f"Execute: {topic}",
                committee_results,
            )

        # Phase 5: Review (Learning)
        if learning_agents:
            committee_results["phases"]["review"] = self._execute_phase(
                WorkflowPhase.REVIEW,
                learning_agents,
                f"Review: {topic}",
                committee_results,
            )

        session.results = committee_results
        return committee_results

    def _execute_phase(self, phase: WorkflowPhase, agents: List[AgentIdentity],
                       task_desc: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a workflow phase with assigned agents."""
        results = {}
        for agent in agents:
            task = Task(
                task_id=f"{phase.value}_{agent.agent_id}",
                domain=self._phase_to_domain(phase),
                description=task_desc,
                context=context,
                priority=MessagePriority.HIGH,
            )
            delegation_result = self.delegation.delegate(task)
            if delegation_result["success"]:
                self.delegation.complete_task(task.task_id, {
                    "agent": agent.name,
                    "role": agent.role.value,
                    "phase": phase.value,
                    "output": f"{agent.name} completed {phase.value}: {task_desc}",
                })
            results[agent.agent_id] = delegation_result
        return results

    def _phase_to_domain(self, phase: WorkflowPhase) -> TaskDomain:
        """Map workflow phase to task domain."""
        mapping = {
            WorkflowPhase.RESEARCH: TaskDomain.RESEARCH,
            WorkflowPhase.ANALYSIS: TaskDomain.STRATEGY,
            WorkflowPhase.DECISION: TaskDomain.PORTFOLIO,
            WorkflowPhase.EXECUTION: TaskDomain.EXECUTION,
            WorkflowPhase.REVIEW: TaskDomain.PERFORMANCE,
            WorkflowPhase.LEARNING: TaskDomain.LEARNING,
        }
        return mapping.get(phase, TaskDomain.CROSS_DOMAIN)

    def get_organization_summary(self) -> Dict[str, Any]:
        """Get summary of the AI organization structure."""
        role_counts = defaultdict(int)
        for agent in self._agents.values():
            role_counts[agent.role.value] += 1

        return {
            "total_agents": len(self._agents),
            "role_distribution": dict(role_counts),
            "active_sessions": len(self._sessions),
            "agents": {aid: a.to_dict() for aid, a in self._agents.items()},
        }

    def get_agent_state(self, agent_id: str) -> Dict[str, Any]:
        """Get current state of an agent."""
        return self._agent_states.get(agent_id, {})

    def update_agent_state(self, agent_id: str, state: Dict[str, Any]):
        """Update agent's shared state."""
        self._agent_states[agent_id].update(state)
