"""Multi Agent Service - orchestrates the full autonomous multi-agent collaboration."""

from typing import Any, Dict, List, Optional

from .message import AgentIdentity, AgentRole, AgentMessage, MessagePriority
from .communication import AgentCommunicationBus
from .delegation import TaskDelegationEngine, Task, TaskDomain, TaskStatus
from .coordinator import AgentCoordinator, CoordinationMode
from .debate import MultiAgentDebateEngine, DebatePosition
from .consensus import ConsensusDecisionEngine, VotingMethod, AgentOpinion, DecisionType
from .reputation import AgentReputationSystem
from .memory import AgentOrganizationMemory
from .workflow import AgentWorkflowEngine
from .learning import OrganizationLearningEngine, LearningDomain


class MultiAgentService:
    """Multi-Agent Collaboration Service.

    Orchestrates the full autonomous multi-agent collaboration loop:
    1. Agent Communication
    2. Task Delegation
    3. Agent Coordination
    4. Multi-Agent Debate
    5. Consensus Decision
    6. Agent Reputation
    7. Organization Memory
    8. Workflow Execution
    9. Organization Learning

    Transforms ICYQuant from a collection of AI modules into an
    AI Investment Organization.
    """

    def __init__(self, coordinator: AgentCoordinator):
        self.coordinator = coordinator
        self.bus = coordinator.bus
        self.delegation = coordinator.delegation
        self.debate = MultiAgentDebateEngine()
        self.consensus = ConsensusDecisionEngine()
        self.reputation = AgentReputationSystem()
        self.memory = AgentOrganizationMemory()
        self.workflow = AgentWorkflowEngine()
        self.learning = OrganizationLearningEngine()

    def run(self, agents: List[AgentIdentity]) -> Dict[str, Any]:
        """Run the multi-agent collaboration.

        Args:
            agents: List of agents to coordinate.

        Returns:
            Dict with collaboration result.
        """
        return self.coordinator.coordinate(agents)

    def run_investment_committee(self, topic: str,
                                  market_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run a full investment committee session.

        This is the primary AI Organization workflow:
        Research → Analysis → Debate → Decision → Execution → Review → Learning

        Args:
            topic: Investment topic to analyze.
            market_data: Market data context.

        Returns:
            Dict with full committee results.
        """
        # Phase 1: Run coordination through investment committee
        committee_result = self.coordinator.run_investment_committee(topic, market_data)

        # Phase 2: Run debate on the topic
        debate_result = self.debate.debate(topic)

        # Phase 3: Consensus decision from agent scores
        consensus = self.consensus.decide_from_scores(
            research_score=0.75,
            risk_score=0.35,
            strategy_score=0.68,
            portfolio_score=0.60,
            topic=topic,
        )

        # Phase 4: Record in organization memory
        agents_list = [a.name for a in self.coordinator._agents.values()]
        if agents_list:
            self.memory.save_decision(
                agents=agents_list,
                description=f"Investment committee decision on {topic}",
                outcome=f"Decision: {consensus.decision.value}, Confidence: {consensus.confidence.value}",
                lesson=f"Committee reached {consensus.decision.value} with {consensus.confidence.value} confidence",
            )

        # Phase 5: Organization learning
        learning_result = self.learning.learn(committee_result)

        return {
            "topic": topic,
            "committee": committee_result,
            "debate": debate_result.to_dict(),
            "consensus": consensus.to_dict(),
            "learning": learning_result,
            "organization_summary": self.coordinator.get_organization_summary(),
        }

    def delegate_and_execute(self, task: Task) -> Dict[str, Any]:
        """Delegate a task and track execution.

        Full task lifecycle:
        Create → Delegate → Execute → Report → Learn

        Args:
            task: The task to delegate.

        Returns:
            Dict with delegation and execution results.
        """
        delegation_result = self.delegation.delegate(task)
        task_result = self.delegation.get_task_status(task.task_id)

        # Record in memory
        if delegation_result["success"]:
            self.memory.save_conversation(
                agents=[delegation_result["assigned_to"]["name"]],
                description=f"Task delegated: {task.description}",
                outcome=f"Assigned to {delegation_result['assigned_to']['name']}",
            )

        return {
            "delegation": delegation_result,
            "task_status": task_result,
        }

    def run_debate_with_consensus(self, topic: str,
                                   bull_arguments: List[Dict[str, Any]],
                                   bear_arguments: List[Dict[str, Any]],
                                   neutral_arguments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run a debate and reach consensus.

        Args:
            topic: Debate topic.
            bull_arguments: Bull case arguments.
            bear_arguments: Bear case arguments.
            neutral_arguments: Neutral perspective arguments.

        Returns:
            Dict with debate and consensus results.
        """
        debate = self.debate.run_full_debate_with_analysts(
            topic, bull_arguments, bear_arguments, neutral_arguments,
        )

        # Convert debate to opinions for consensus
        opinions = []
        for arg in bull_arguments:
            opinions.append(AgentOpinion(
                agent_id="bull_analyst",
                agent_name="Bull Analyst",
                agent_role="RESEARCH",
                decision=DecisionType.BUY,
                confidence=arg.get("confidence", 0.6),
                reasoning=arg["statement"],
                score=arg.get("confidence", 0.6),
            ))
        for arg in bear_arguments:
            opinions.append(AgentOpinion(
                agent_id="bear_analyst",
                agent_name="Bear Analyst",
                agent_role="RESEARCH",
                decision=DecisionType.SELL,
                confidence=arg.get("confidence", 0.6),
                reasoning=arg["statement"],
                score=1 - arg.get("confidence", 0.6),
            ))

        consensus = self.consensus.decide(opinions, VotingMethod.WEIGHTED)

        # Learn from the process
        self.learning.record_observation(
            domain=LearningDomain.DECISION_QUALITY,
            description=f"Debate and consensus on: {topic}",
            source_agents=["bull_analyst", "bear_analyst"],
            impact=consensus.agreement_level,
        )

        return {
            "topic": topic,
            "debate": debate.to_dict(),
            "consensus": consensus.to_dict(),
        }

    def get_organization_report(self) -> Dict[str, Any]:
        """Get a comprehensive organization status report."""
        return {
            "organization": self.coordinator.get_organization_summary(),
            "communication": self.bus.get_delivery_stats(),
            "reputation": self.reputation.get_organization_reputation_summary(),
            "learning": self.learning.generate_report(),
            "memory_knowledge": self.memory.get_knowledge_summary(),
        }
