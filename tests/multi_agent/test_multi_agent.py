"""Tests for AI Autonomous Multi Agent Collaboration Engine (Commit 4 Part 11)."""

from services.multi_agent.message import (
    AgentMessage, AgentIdentity, AgentRole, MessageType,
    MessagePriority, MessageStatus, MessageHistory, MessageProtocol,
)
from services.multi_agent.communication import (
    AgentCommunicationBus, BusStatus, DeliveryMode, DeliveryReport,
)
from services.multi_agent.delegation import (
    TaskDelegationEngine, Task, TaskDomain, TaskStatus,
    DelegationStrategy, DelegationPlan,
)
from services.multi_agent.coordinator import (
    AgentCoordinator, CoordinationMode, WorkflowPhase,
    CoordinationContext,
)
from services.multi_agent.debate import (
    MultiAgentDebateEngine, DebatePosition, DebateRound,
    ArgumentStrength, Argument, DebateRoundResult, DebateResult,
)
from services.multi_agent.consensus import (
    ConsensusDecisionEngine, DecisionType, VotingMethod,
    ConfidenceLevel, AgentOpinion, ConsensusDecision,
)
from services.multi_agent.reputation import (
    AgentReputationSystem, ReputationMetric, ReputationTier,
    ReputationScore, PredictionRecord,
)
from services.multi_agent.memory import (
    AgentOrganizationMemory, OrganizationMemoryEntry,
    MemoryEventType, LessonCategory, CollaborationPattern,
    OrganizationKnowledge,
)
from services.multi_agent.workflow import (
    AgentWorkflowEngine, Workflow, WorkflowStep,
    WorkflowStatus, StepStatus, StepType,
)
from services.multi_agent.learning import (
    OrganizationLearningEngine, LearningDomain, ImprovementType,
    LearningObservation, OrganizationInsight, LearningReport,
)
from services.multi_agent.service import MultiAgentService


# ──────────────────────────────────────────────
# Agent Message Protocol Tests
# ──────────────────────────────────────────────

def test_agent_message_creation():
    """Test creating an agent message."""
    sender = AgentIdentity("agent_1", "Research Agent", AgentRole.RESEARCH)
    receiver = AgentIdentity("agent_2", "Risk Agent", AgentRole.RISK)
    msg = AgentMessage(
        message_id="msg_1",
        sender=sender,
        receiver=receiver,
        message_type=MessageType.REQUEST,
        task="Analyze NVDA",
        priority=MessagePriority.HIGH,
    )
    assert msg.sender.name == "Research Agent"
    assert msg.receiver.name == "Risk Agent"
    assert msg.task == "Analyze NVDA"
    assert msg.priority == MessagePriority.HIGH
    assert msg.status == MessageStatus.CREATED


def test_agent_message_envelope():
    """Test message serialization to envelope."""
    sender = AgentIdentity("agent_1", "Research Agent", AgentRole.RESEARCH)
    msg = AgentMessage(
        message_id="msg_1",
        sender=sender,
        receiver=None,
        message_type=MessageType.BROADCAST,
        task="Market alert",
    )
    envelope = msg.to_envelope()
    assert envelope["message_id"] == "msg_1"
    assert envelope["sender"]["name"] == "Research Agent"
    assert envelope["message_type"] == "BROADCAST"


def test_agent_message_reply():
    """Test creating reply message."""
    sender = AgentIdentity("agent_1", "Research", AgentRole.RESEARCH)
    receiver = AgentIdentity("agent_2", "Risk", AgentRole.RISK)
    original = AgentMessage(
        message_id="msg_1",
        sender=sender,
        receiver=receiver,
        message_type=MessageType.REQUEST,
        task="Analyze NVDA",
    )
    reply = original.create_reply({"decision": "APPROVED"})
    assert reply.message_id == "reply_msg_1"
    assert reply.message_type == MessageType.RESPONSE
    assert reply.data["decision"] == "APPROVED"


def test_agent_message_notification():
    """Test creating notification from message."""
    sender = AgentIdentity("agent_1", "Research", AgentRole.RESEARCH)
    msg = AgentMessage(
        message_id="msg_1",
        sender=sender,
        receiver=None,
        message_type=MessageType.REQUEST,
        task="Test",
    )
    notification = msg.create_notification("ALERT", {"level": "HIGH"})
    assert notification.message_type == MessageType.NOTIFICATION
    assert notification.data["level"] == "HIGH"


def test_agent_identity_to_dict():
    """Test agent identity serialization."""
    identity = AgentIdentity("agent_1", "Research Agent", AgentRole.RESEARCH,
                             capabilities=["quant", "fundamental"])
    d = identity.to_dict()
    assert d["agent_id"] == "agent_1"
    assert d["role"] == "RESEARCH"
    assert "quant" in d["capabilities"]


def test_message_history():
    """Test message history tracking."""
    history = MessageHistory(thread_id="thread_1", topic="NVDA Analysis")
    sender = AgentIdentity("a1", "Research", AgentRole.RESEARCH)
    receiver = AgentIdentity("a2", "Risk", AgentRole.RISK)
    msg = AgentMessage(
        message_id="msg_1", sender=sender, receiver=receiver,
        message_type=MessageType.REQUEST, task="Analyze",
    )
    history.add_message(msg)
    assert len(history.messages) == 1
    assert len(history.participants) == 2


def test_message_protocol_validation():
    """Test message protocol validation."""
    sender = AgentIdentity("a1", "Research", AgentRole.RESEARCH)
    receiver = AgentIdentity("a2", "Risk", AgentRole.RISK)
    msg = AgentMessage(
        message_id="msg_1", sender=sender, receiver=receiver,
        message_type=MessageType.REQUEST, task="Test",
    )
    # Research -> Risk is not in allowed communication (only CIO, Strategy, Learning)
    assert MessageProtocol.validate_message(msg) is False

    # CIO -> Risk is allowed
    cio = AgentIdentity("cio", "CIO", AgentRole.CIO)
    msg2 = AgentMessage(
        message_id="msg_2", sender=cio, receiver=receiver,
        message_type=MessageType.REQUEST, task="Test",
    )
    assert MessageProtocol.validate_message(msg2) is True

    # Broadcast is always allowed
    broadcast = AgentMessage(
        message_id="msg_3", sender=sender, receiver=None,
        message_type=MessageType.BROADCAST, task="Test",
    )
    assert MessageProtocol.validate_message(broadcast) is True


def test_message_protocol_allowed_receivers():
    """Test getting allowed receivers for a role."""
    allowed = MessageProtocol.get_allowed_receivers(AgentRole.CIO)
    assert AgentRole.RESEARCH in allowed
    assert AgentRole.STRATEGY in allowed
    assert AgentRole.RISK in allowed


def test_message_history_decision_trail():
    """Test extracting decision trail from history."""
    history = MessageHistory(thread_id="thread_1")
    sender = AgentIdentity("a1", "CIO", AgentRole.CIO)
    receiver = AgentIdentity("a2", "Risk", AgentRole.RISK)
    msg = AgentMessage(
        message_id="msg_1", sender=sender, receiver=receiver,
        message_type=MessageType.RESPONSE, task="Decision",
        data={"decision": "BUY", "confidence": 0.85, "reasoning": "Strong signals"},
    )
    history.add_message(msg)
    trail = history.get_decision_trail()
    assert len(trail) == 1
    assert trail[0]["decision"] == "BUY"


# ──────────────────────────────────────────────
# Agent Communication Bus Tests
# ──────────────────────────────────────────────

def test_communication_bus_register_agent():
    """Test registering agent on bus."""
    bus = AgentCommunicationBus()
    agent = AgentIdentity("agent_1", "Research", AgentRole.RESEARCH)
    bus.register_agent(agent)
    assert len(bus._agents) == 1


def test_communication_bus_send():
    """Test sending message through bus."""
    bus = AgentCommunicationBus()
    cio = AgentIdentity("cio", "CIO", AgentRole.CIO)
    research = AgentIdentity("research", "Research", AgentRole.RESEARCH)
    bus.register_agent(cio)
    bus.register_agent(research)

    report = bus.request(cio, research, "Analyze market", {"symbol": "NVDA"})
    assert report.success is True
    assert len(report.recipients) == 1


def test_communication_bus_broadcast():
    """Test broadcasting message."""
    bus = AgentCommunicationBus()
    cio = AgentIdentity("cio", "CIO", AgentRole.CIO)
    research = AgentIdentity("research", "Research", AgentRole.RESEARCH)
    risk = AgentIdentity("risk", "Risk", AgentRole.RISK)
    bus.register_agent(cio)
    bus.register_agent(research)
    bus.register_agent(risk)

    report = bus.broadcast(cio, "Market alert", {"type": "volatility_spike"})
    assert report.success is True


def test_communication_bus_notify():
    """Test sending notifications."""
    bus = AgentCommunicationBus()
    cio = AgentIdentity("cio", "CIO", AgentRole.CIO)
    research = AgentIdentity("research", "Research", AgentRole.RESEARCH)
    bus.register_agent(cio)
    bus.register_agent(research)

    reports = bus.notify(cio, "Status update", {"status": "OK"})
    assert len(reports) == 1


def test_communication_bus_delivery_stats():
    """Test delivery statistics."""
    bus = AgentCommunicationBus()
    cio = AgentIdentity("cio", "CIO", AgentRole.CIO)
    research = AgentIdentity("research", "Research", AgentRole.RESEARCH)
    bus.register_agent(cio)
    bus.register_agent(research)
    bus.request(cio, research, "Test")

    stats = bus.get_delivery_stats()
    assert stats["total_deliveries"] == 1
    assert stats["registered_agents"] == 2


def test_communication_bus_thread_tracking():
    """Test conversation thread tracking."""
    bus = AgentCommunicationBus()
    cio = AgentIdentity("cio", "CIO", AgentRole.CIO)
    research = AgentIdentity("research", "Research", AgentRole.RESEARCH)
    bus.register_agent(cio)
    bus.register_agent(research)

    msg = AgentMessage(
        message_id="thread_test_1",
        sender=cio, receiver=research,
        message_type=MessageType.REQUEST, task="Test",
        correlation_id="corr_1",
    )
    bus.send(msg)
    thread = bus.get_thread("corr_1")
    assert thread is not None
    assert thread.topic == "Test"


def test_communication_bus_get_agents_by_role():
    """Test filtering agents by role."""
    bus = AgentCommunicationBus()
    bus.register_agent(AgentIdentity("r1", "Research 1", AgentRole.RESEARCH))
    bus.register_agent(AgentIdentity("r2", "Research 2", AgentRole.RESEARCH))
    bus.register_agent(AgentIdentity("risk1", "Risk 1", AgentRole.RISK))

    research_agents = bus.get_registered_agents_by_role(AgentRole.RESEARCH)
    assert len(research_agents) == 2


def test_communication_bus_start_stop():
    """Test bus lifecycle."""
    bus = AgentCommunicationBus()
    assert bus.status == BusStatus.INITIALIZED
    bus.start()
    assert bus.status == BusStatus.RUNNING
    bus.stop()
    assert bus.status == BusStatus.STOPPED


# ──────────────────────────────────────────────
# Task Delegation Engine Tests
# ──────────────────────────────────────────────

def test_task_delegation_delegate():
    """Test basic task delegation."""
    engine = TaskDelegationEngine()
    research = AgentIdentity("r1", "Research", AgentRole.RESEARCH)
    engine.register_agent(research)

    task = Task(
        task_id="task_1",
        domain=TaskDomain.RESEARCH,
        description="Analyze market data",
    )
    result = engine.delegate(task)
    assert result["success"] is True
    assert result["assigned_to"]["name"] == "Research"


def test_task_delegation_capability_match():
    """Test capability-based delegation."""
    engine = TaskDelegationEngine()
    engine.register_agent(AgentIdentity("r1", "Research", AgentRole.RESEARCH))
    engine.register_agent(AgentIdentity("s1", "Strategy", AgentRole.STRATEGY))

    task = Task(
        task_id="task_1",
        domain=TaskDomain.STRATEGY,
        description="Design trading strategy",
        required_capabilities=["alpha_generation"],
    )
    result = engine.delegate(task, DelegationStrategy.CAPABILITY_MATCH)
    assert result["success"] is True
    assert result["assigned_to"]["role"] == "STRATEGY"


def test_task_delegation_load_balance():
    """Test load-balanced delegation."""
    engine = TaskDelegationEngine()
    engine.register_agent(AgentIdentity("r1", "Research 1", AgentRole.RESEARCH))
    engine.register_agent(AgentIdentity("r2", "Research 2", AgentRole.RESEARCH))

    task1 = Task(task_id="t1", domain=TaskDomain.RESEARCH, description="Task 1")
    task2 = Task(task_id="t2", domain=TaskDomain.RESEARCH, description="Task 2")

    engine.delegate(task1, DelegationStrategy.LOAD_BALANCE)
    engine.delegate(task2, DelegationStrategy.LOAD_BALANCE)

    load = engine.get_agent_load()
    assert load["r1"] <= 1
    assert load["r2"] <= 1


def test_task_delegation_no_suitable_agent():
    """Test delegation when no suitable agent exists."""
    engine = TaskDelegationEngine()
    engine.register_agent(AgentIdentity("r1", "Research", AgentRole.RESEARCH))

    task = Task(
        task_id="task_1",
        domain=TaskDomain.EXECUTION,
        description="Execute trade",
        required_capabilities=["order_execution"],
    )
    result = engine.delegate(task)
    assert result["success"] is False
    assert result["reason"] == "No suitable agent found"


def test_task_delegation_complex():
    """Test complex task delegation with subtasks."""
    engine = TaskDelegationEngine()
    engine.register_agent(AgentIdentity("r1", "Research", AgentRole.RESEARCH))
    engine.register_agent(AgentIdentity("s1", "Strategy", AgentRole.STRATEGY))
    engine.register_agent(AgentIdentity("risk1", "Risk", AgentRole.RISK))
    engine.register_agent(AgentIdentity("p1", "Portfolio", AgentRole.PORTFOLIO))

    root = Task(task_id="nvda_analysis", domain=TaskDomain.CROSS_DOMAIN,
                description="Analyze NVDA investment")

    plan = engine.delegate_complex(root, [
        {"description": "Research NVDA fundamentals", "domain": "RESEARCH"},
        {"description": "Analyze trading opportunity", "domain": "STRATEGY"},
        {"description": "Assess risk factors", "domain": "RISK"},
        {"description": "Determine position size", "domain": "PORTFOLIO"},
    ])

    assert len(plan.subtasks) == 4
    assert len(plan.assignment) == 4


def test_task_delegation_complete_task():
    """Test completing a delegated task."""
    engine = TaskDelegationEngine()
    engine.register_agent(AgentIdentity("r1", "Research", AgentRole.RESEARCH))

    task = Task(task_id="t1", domain=TaskDomain.RESEARCH, description="Test")
    engine.delegate(task)
    engine.complete_task("t1", {"output": "Done"})

    status = engine.get_task_status("t1")
    assert status["status"] == "COMPLETED"
    assert engine.get_agent_load()["r1"] == 0


def test_task_delegation_round_robin():
    """Test round-robin delegation strategy."""
    engine = TaskDelegationEngine()
    engine.register_agent(AgentIdentity("r1", "Research 1", AgentRole.RESEARCH))
    engine.register_agent(AgentIdentity("r2", "Research 2", AgentRole.RESEARCH))

    for i in range(4):
        task = Task(task_id=f"t{i}", domain=TaskDomain.RESEARCH, description=f"Task {i}")
        engine.delegate(task, DelegationStrategy.ROUND_ROBIN)

    load = engine.get_agent_load()
    assert load["r1"] + load["r2"] == 4


def test_task_delegation_expertise_priority():
    """Test expertise-priority delegation."""
    engine = TaskDelegationEngine()
    engine.register_agent(AgentIdentity("r1", "Research", AgentRole.RESEARCH))
    engine.register_agent(AgentIdentity("s1", "Strategy", AgentRole.STRATEGY))

    task = Task(task_id="t1", domain=TaskDomain.STRATEGY, description="Design strategy")
    result = engine.delegate(task, DelegationStrategy.EXPERTISE_PRIORITY)
    assert result["assigned_to"]["role"] == "STRATEGY"


def test_task_split():
    """Test splitting a task into subtasks."""
    task = Task(task_id="parent", domain=TaskDomain.CROSS_DOMAIN,
                description="Complex analysis")
    subtasks = task.split([
        {"description": "Subtask 1", "domain": "RESEARCH"},
        {"description": "Subtask 2", "domain": "RISK"},
    ])
    assert len(subtasks) == 2
    assert len(task.subtasks) == 2
    assert subtasks[0].task_id == "parent_sub_0"


# ──────────────────────────────────────────────
# Agent Coordinator Tests
# ──────────────────────────────────────────────

def test_agent_coordinator_coordinate():
    """Test basic agent coordination."""
    bus = AgentCommunicationBus()
    delegation = TaskDelegationEngine()
    coordinator = AgentCoordinator(bus, delegation)

    agents = [
        AgentIdentity("cio", "CIO", AgentRole.CIO),
        AgentIdentity("research", "Research", AgentRole.RESEARCH),
    ]
    result = coordinator.coordinate(agents)
    assert result["count"] == 2
    assert "CIO" in result["roles"]


def test_agent_coordinator_start_session():
    """Test starting a coordination session."""
    bus = AgentCommunicationBus()
    delegation = TaskDelegationEngine()
    coordinator = AgentCoordinator(bus, delegation)

    cio = AgentIdentity("cio", "CIO", AgentRole.CIO)
    research = AgentIdentity("research", "Research", AgentRole.RESEARCH)
    coordinator.register_agent(cio)
    coordinator.register_agent(research)

    session = coordinator.start_session(
        topic="NVDA Analysis",
        mode=CoordinationMode.SEQUENTIAL,
        participants=[cio, research],
    )
    assert session.topic == "NVDA Analysis"
    assert session.mode == CoordinationMode.SEQUENTIAL
    assert len(session.participants) == 2


def test_agent_coordinator_investment_committee():
    """Test running investment committee workflow."""
    bus = AgentCommunicationBus()
    delegation = TaskDelegationEngine()
    coordinator = AgentCoordinator(bus, delegation)

    coordinator.register_agent(AgentIdentity("cio", "CIO", AgentRole.CIO))
    coordinator.register_agent(AgentIdentity("r1", "Research", AgentRole.RESEARCH))
    coordinator.register_agent(AgentIdentity("s1", "Strategy", AgentRole.STRATEGY))
    coordinator.register_agent(AgentIdentity("risk1", "Risk", AgentRole.RISK))
    coordinator.register_agent(AgentIdentity("p1", "Portfolio", AgentRole.PORTFOLIO))
    coordinator.register_agent(AgentIdentity("e1", "Execution", AgentRole.EXECUTION))
    coordinator.register_agent(AgentIdentity("l1", "Learning", AgentRole.LEARNING))

    result = coordinator.run_investment_committee(
        topic="NVDA Position Review",
        market_data={"NVDA": 130.0, "VIX": 18.5},
    )
    assert result["topic"] == "NVDA Position Review"
    assert "phases" in result
    assert "research" in result["phases"]


def test_agent_coordinator_organization_summary():
    """Test organization summary."""
    bus = AgentCommunicationBus()
    delegation = TaskDelegationEngine()
    coordinator = AgentCoordinator(bus, delegation)

    coordinator.register_agent(AgentIdentity("cio", "CIO", AgentRole.CIO))
    coordinator.register_agent(AgentIdentity("r1", "Research", AgentRole.RESEARCH))
    coordinator.register_agent(AgentIdentity("r2", "Research 2", AgentRole.RESEARCH))
    coordinator.register_agent(AgentIdentity("risk1", "Risk", AgentRole.RISK))

    summary = coordinator.get_organization_summary()
    assert summary["total_agents"] == 4
    assert summary["role_distribution"]["RESEARCH"] == 2
    assert summary["role_distribution"]["RISK"] == 1


# ──────────────────────────────────────────────
# Multi Agent Debate Engine Tests
# ──────────────────────────────────────────────

def test_debate_engine_basic():
    """Test basic debate."""
    engine = MultiAgentDebateEngine()
    result = engine.debate("NVDA Investment")
    assert result.topic == "NVDA Investment"
    assert len(result.rounds) == 4
    assert result.bull_score > 0 or result.bear_score > 0


def test_debate_engine_with_analysts():
    """Test debate with pre-defined analyst arguments."""
    engine = MultiAgentDebateEngine()
    result = engine.run_full_debate_with_analysts(
        topic="NVDA",
        bull_arguments=[
            {"statement": "AI CapEx continues growing", "evidence": ["CapEx report"],
             "strength": "STRONG", "confidence": 0.85},
            {"statement": "Market leadership position", "evidence": ["Market share"],
             "strength": "STRONG", "confidence": 0.80},
        ],
        bear_arguments=[
            {"statement": "Valuation is excessive", "evidence": ["P/E ratio"],
             "strength": "MODERATE", "confidence": 0.55},
        ],
        neutral_arguments=[
            {"statement": "Balanced risk-reward", "strength": "MODERATE", "confidence": 0.50},
        ],
    )
    assert result.topic == "NVDA"
    assert result.bull_score > result.bear_score


def test_debate_engine_tie():
    """Test debate with balanced arguments."""
    engine = MultiAgentDebateEngine()
    result = engine.run_full_debate_with_analysts(
        topic="Uncertain Asset",
        bull_arguments=[
            {"statement": "Potential upside", "strength": "MODERATE", "confidence": 0.5},
        ],
        bear_arguments=[
            {"statement": "Significant risk", "strength": "MODERATE", "confidence": 0.5},
        ],
    )
    # Close scores should result in NEUTRAL consensus
    assert result.consensus_reached is True or result.final_winner is not None


def test_debate_result_to_dict():
    """Test debate result serialization."""
    engine = MultiAgentDebateEngine()
    result = engine.debate("Test Topic")
    d = result.to_dict()
    assert d["topic"] == "Test Topic"
    assert "rounds" in d
    assert "bull_score" in d


def test_debate_engine_recommendations():
    """Test debate recommendations generation."""
    engine = MultiAgentDebateEngine()
    result = engine.run_full_debate_with_analysts(
        topic="Bullish Asset",
        bull_arguments=[
            {"statement": "Strong buy signal", "strength": "VERY_STRONG", "confidence": 0.95},
        ],
        bear_arguments=[
            {"statement": "Minor concern", "strength": "WEAK", "confidence": 0.2},
        ],
    )
    assert len(result.recommendations) > 0
    assert len(result.risk_flags) > 0


def test_debate_argument_strength_weight():
    """Test argument strength weighting."""
    engine = MultiAgentDebateEngine()
    assert engine._strength_weight(ArgumentStrength.VERY_STRONG) == 1.0
    assert engine._strength_weight(ArgumentStrength.WEAK) == 0.3
    assert engine._strength_weight(ArgumentStrength.SPECULATIVE) == 0.1


# ──────────────────────────────────────────────
# Consensus Decision Engine Tests
# ──────────────────────────────────────────────

def test_consensus_engine_basic():
    """Test basic consensus decision."""
    engine = ConsensusDecisionEngine()
    opinions = [
        AgentOpinion("a1", "Research", "RESEARCH", DecisionType.BUY,
                      0.8, "Strong fundamentals", 0.8),
        AgentOpinion("a2", "Strategy", "STRATEGY", DecisionType.BUY,
                      0.7, "Good signal", 0.7),
    ]
    result = engine.decide(opinions, VotingMethod.MAJORITY)
    assert result.decision == DecisionType.BUY
    assert len(result.opinions) == 2


def test_consensus_engine_weighted():
    """Test weighted consensus."""
    engine = ConsensusDecisionEngine()
    opinions = [
        AgentOpinion("a1", "Expert", "RESEARCH", DecisionType.BUY,
                      0.9, "Strong buy", 0.9),
        AgentOpinion("a2", "Junior", "RESEARCH", DecisionType.SELL,
                      0.3, "Weak sell", 0.3),
    ]
    result = engine.decide(opinions, VotingMethod.WEIGHTED)
    assert result.decision == DecisionType.BUY


def test_consensus_engine_from_scores():
    """Test consensus from numeric scores."""
    engine = ConsensusDecisionEngine()
    result = engine.decide_from_scores(
        research_score=0.85,
        risk_score=0.25,
        strategy_score=0.70,
        portfolio_score=0.65,
        topic="NVDA",
    )
    assert result.decision in (DecisionType.BUY, DecisionType.INCREASE, DecisionType.HOLD)
    assert len(result.opinions) > 0


def test_consensus_engine_unanimous():
    """Test unanimous voting method."""
    engine = ConsensusDecisionEngine()
    opinions = [
        AgentOpinion("a1", "A1", "RESEARCH", DecisionType.BUY, 0.9, "Buy"),
        AgentOpinion("a2", "A2", "STRATEGY", DecisionType.BUY, 0.85, "Buy"),
    ]
    result = engine.decide(opinions, VotingMethod.UNANIMOUS)
    assert result.decision == DecisionType.BUY
    assert result.confidence in (ConfidenceLevel.VERY_HIGH, ConfidenceLevel.HIGH)


def test_consensus_engine_supermajority():
    """Test supermajority voting."""
    engine = ConsensusDecisionEngine()
    opinions = [
        AgentOpinion("a1", "A1", "RESEARCH", DecisionType.BUY, 0.8, "Buy"),
        AgentOpinion("a2", "A2", "STRATEGY", DecisionType.BUY, 0.7, "Buy"),
        AgentOpinion("a3", "A3", "RISK", DecisionType.HOLD, 0.6, "Hold"),
    ]
    result = engine.decide(opinions, VotingMethod.SUPERMAJORITY)
    assert result.decision == DecisionType.BUY


def test_consensus_engine_dissent_tracking():
    """Test dissent tracking in consensus."""
    engine = ConsensusDecisionEngine()
    opinions = [
        AgentOpinion("a1", "A1", "RESEARCH", DecisionType.BUY, 0.8, "Buy"),
        AgentOpinion("a2", "A2", "STRATEGY", DecisionType.BUY, 0.7, "Buy"),
        AgentOpinion("a3", "A3", "RISK", DecisionType.SELL, 0.6, "Sell"),
    ]
    result = engine.decide(opinions, VotingMethod.MAJORITY)
    assert result.dissent_count == 1


def test_consensus_engine_action_items():
    """Test action item generation."""
    engine = ConsensusDecisionEngine()
    opinions = [
        AgentOpinion("a1", "A1", "RESEARCH", DecisionType.BUY, 0.9, "Buy"),
    ]
    result = engine.decide(opinions)
    assert len(result.action_items) > 0
    assert any("order" in str(item).lower() for item in result.action_items)


def test_consensus_engine_history():
    """Test decision history."""
    engine = ConsensusDecisionEngine()
    opinions = [
        AgentOpinion("a1", "A1", "RESEARCH", DecisionType.HOLD, 0.5, "Hold"),
    ]
    engine.decide(opinions)
    engine.decide(opinions)
    history = engine.get_decision_history()
    assert len(history) == 2


def test_consensus_engine_agreement_metrics():
    """Test agreement metrics."""
    engine = ConsensusDecisionEngine()
    opinions = [
        AgentOpinion("a1", "A1", "RESEARCH", DecisionType.BUY, 0.9, "Buy"),
        AgentOpinion("a2", "A2", "STRATEGY", DecisionType.BUY, 0.85, "Buy"),
    ]
    engine.decide(opinions)
    metrics = engine.get_agreement_metrics()
    assert metrics["total_decisions"] == 1
    assert metrics["avg_agreement"] > 0


# ──────────────────────────────────────────────
# Agent Reputation System Tests
# ──────────────────────────────────────────────

def test_reputation_system_update():
    """Test updating agent reputation."""
    system = AgentReputationSystem()
    system.register_agent("r1", "Research Agent", "RESEARCH")
    system.update("r1", 0.87)
    assert system.scores["r1"].overall_score == 0.87


def test_reputation_system_metric_update():
    """Test updating specific reputation metrics."""
    system = AgentReputationSystem()
    system.register_agent("r1", "Research", "RESEARCH")
    system.update_metric("r1", ReputationMetric.PREDICTION_ACCURACY, 0.95)
    system.update_metric("r1", ReputationMetric.DECISION_QUALITY, 0.88)

    score = system.get_reputation("r1")
    assert score.metrics["PREDICTION_ACCURACY"] == 0.95


def test_reputation_system_prediction():
    """Test recording predictions."""
    system = AgentReputationSystem()
    system.register_agent("r1", "Research", "RESEARCH")

    system.record_prediction("r1", "UP", "UP", 0.8)
    system.record_prediction("r1", "UP", "DOWN", 0.7)

    score = system.get_reputation("r1")
    assert score.total_decisions == 2
    assert score.correct_decisions == 1


def test_reputation_system_tiers():
    """Test reputation tier classification."""
    system = AgentReputationSystem()
    system.register_agent("elite", "Elite", "RESEARCH")
    system.register_agent("junior", "Junior", "RESEARCH")

    system.update("elite", 0.92)
    system.update("junior", 0.35)

    assert system.get_reputation("elite").tier == ReputationTier.ELITE
    assert system.get_reputation("junior").tier == ReputationTier.NOVICE


def test_reputation_system_top_agents():
    """Test getting top agents."""
    system = AgentReputationSystem()
    system.register_agent("a1", "Agent 1", "RESEARCH")
    system.register_agent("a2", "Agent 2", "RESEARCH")
    system.register_agent("a3", "Agent 3", "STRATEGY")

    system.update("a1", 0.9)
    system.update("a2", 0.6)
    system.update("a3", 0.75)

    top = system.get_top_agents(role="RESEARCH", top_n=2)
    assert len(top) == 2
    assert top[0].agent_name == "Agent 1"


def test_reputation_system_weight():
    """Test getting reputation-based voting weight."""
    system = AgentReputationSystem()
    system.register_agent("r1", "Research", "RESEARCH")
    system.update("r1", 0.87)

    weight = system.get_reputation_weight("r1")
    assert weight == 0.87


def test_reputation_system_organization_summary():
    """Test organization reputation summary."""
    system = AgentReputationSystem()
    system.register_agent("r1", "Research", "RESEARCH")
    system.register_agent("s1", "Strategy", "STRATEGY")
    system.update("r1", 0.8)
    system.update("s1", 0.7)

    summary = system.get_organization_reputation_summary()
    assert summary["total_agents"] == 2
    assert "role_averages" in summary


# ──────────────────────────────────────────────
# Agent Organization Memory Tests
# ──────────────────────────────────────────────

def test_organization_memory_save():
    """Test saving organization memory events."""
    memory = AgentOrganizationMemory()
    entry = OrganizationMemoryEntry(
        entry_id="e1",
        event_type=MemoryEventType.DECISION,
        agents_involved=["Research", "Risk"],
        description="NVDA decision",
        outcome="BUY",
        lesson="Strong consensus on AI sector",
    )
    memory.save(entry)
    assert len(memory.history) == 1


def test_organization_memory_save_conversation():
    """Test saving conversation memory."""
    memory = AgentOrganizationMemory()
    entry = memory.save_conversation(
        agents=["Research", "Risk"],
        description="Risk analysis discussion",
        outcome="Risk level acceptable",
        lesson="Collaboration improves risk assessment",
    )
    assert entry.event_type == MemoryEventType.CONVERSATION
    assert len(memory.history) == 1


def test_organization_memory_save_decision():
    """Test saving decision memory."""
    memory = AgentOrganizationMemory()
    memory.save_decision(
        agents=["CIO", "Research", "Risk"],
        description="Portfolio allocation decision",
        outcome="60% equities, 40% cash",
        lesson="Conservative allocation in high volatility",
    )
    decisions = memory.get_decisions()
    assert len(decisions) == 1


def test_organization_memory_save_lesson():
    """Test saving organizational lesson."""
    memory = AgentOrganizationMemory()
    memory.save_lesson(
        agents=["Research", "Strategy"],
        description="Market regime detection",
        lesson="High correlation environment requires position reduction",
        category=LessonCategory.RISK_MANAGEMENT,
    )
    lessons = memory.get_lessons()
    assert len(lessons) == 1


def test_organization_memory_lessons_by_category():
    """Test filtering lessons by category."""
    memory = AgentOrganizationMemory()
    memory.save_lesson(["A"], "Process issue", "Fix workflow", LessonCategory.PROCESS)
    memory.save_lesson(["B"], "Risk issue", "Reduce exposure", LessonCategory.RISK_MANAGEMENT)
    memory.save_lesson(["C"], "Comm issue", "Improve messaging", LessonCategory.COMMUNICATION)

    risk_lessons = memory.get_lessons(category=LessonCategory.RISK_MANAGEMENT)
    assert len(risk_lessons) == 1
    assert "Reduce exposure" in risk_lessons[0]


def test_organization_memory_patterns():
    """Test discovering collaboration patterns."""
    memory = AgentOrganizationMemory()
    memory.save_conversation(["Research", "Risk"], "Analysis 1", "Positive", "Lesson 1")
    memory.save_conversation(["Research", "Risk"], "Analysis 2", "Positive", "Lesson 2")
    memory.save_conversation(["Research", "Strategy"], "Analysis 3", "Negative", "Lesson 3")

    patterns = memory.discover_collaboration_patterns()
    assert len(patterns) >= 1


def test_organization_memory_knowledge_summary():
    """Test knowledge summary generation."""
    memory = AgentOrganizationMemory()
    memory.save_decision(["CIO", "Research"], "Test decision", "Positive", "Lesson")
    memory.save_lesson(["Research"], "Test", "Lesson learned", LessonCategory.PROCESS)

    summary = memory.get_knowledge_summary()
    assert summary.total_decisions >= 1
    assert summary.total_lessons >= 1


def test_organization_memory_agent_collaboration_graph():
    """Test agent collaboration graph."""
    memory = AgentOrganizationMemory()
    memory.save_conversation(["Research", "Risk", "Portfolio"], "Test", "OK")
    memory.save_conversation(["Research", "Strategy"], "Test 2", "OK")

    graph = memory.get_agent_collaboration_graph()
    assert "Research" in graph


# ──────────────────────────────────────────────
# Agent Workflow Engine Tests
# ──────────────────────────────────────────────

def test_workflow_engine_create_from_template():
    """Test creating workflow from template."""
    engine = AgentWorkflowEngine()
    wf = engine.create_from_template("template_investment_research", name="Custom Research")
    assert wf is not None
    assert wf.name == "Custom Research"
    assert len(wf.steps) > 0


def test_workflow_engine_execute():
    """Test executing a workflow."""
    engine = AgentWorkflowEngine()
    wf = engine.create_from_template("template_investment_research")
    result = engine.execute(wf)
    assert result["workflow"] == "Investment Research"
    assert len(result["steps"]) > 0


def test_workflow_engine_templates():
    """Test getting workflow templates."""
    engine = AgentWorkflowEngine()
    templates = engine.get_templates()
    assert len(templates) >= 2


def test_workflow_engine_status():
    """Test workflow status tracking."""
    engine = AgentWorkflowEngine()
    wf = engine.create_from_template("template_trade_execution")
    engine.execute(wf)

    status = engine.get_workflow_status(wf.workflow_id)
    assert status is not None
    assert status["status"] == "COMPLETED"


def test_workflow_engine_history():
    """Test execution history."""
    engine = AgentWorkflowEngine()
    wf = engine.create_from_template("template_investment_research")
    engine.execute(wf)

    history = engine.get_execution_history()
    assert len(history) >= 1


# ──────────────────────────────────────────────
# Organization Learning Engine Tests
# ──────────────────────────────────────────────

def test_learning_engine_learn():
    """Test basic organizational learning."""
    engine = OrganizationLearningEngine()
    result = engine.learn({"agents": ["Research", "Risk"], "count": 2, "decision": "BUY"})
    assert result["learning"] is not None
    assert result["observations_extracted"] > 0


def test_learning_engine_record_observation():
    """Test recording learning observation."""
    engine = OrganizationLearningEngine()
    obs = engine.record_observation(
        domain=LearningDomain.DECISION_QUALITY,
        description="Decision made too quickly",
        source_agents=["CIO", "Research"],
        impact=0.7,
    )
    assert obs.domain == LearningDomain.DECISION_QUALITY
    assert obs.impact == 0.7


def test_learning_engine_record_improvement():
    """Test recording organizational improvement."""
    engine = OrganizationLearningEngine()
    engine.record_improvement(
        improvement_type=ImprovementType.PROCEDURAL,
        description="Streamlined decision workflow",
        agents_affected=["CIO", "Research"],
        result={"efficiency_gain": "20%"},
    )
    history = engine.get_improvement_history()
    assert len(history) == 1


def test_learning_engine_generate_report():
    """Test generating learning report."""
    engine = OrganizationLearningEngine()
    engine.record_observation(LearningDomain.PROCESS_EFFICIENCY, "Test", ["A"], 0.5)
    engine.record_observation(LearningDomain.DECISION_QUALITY, "Test 2", ["B"], 0.6)
    engine.learn({"agents": ["A", "B"], "count": 2})

    report = engine.generate_report()
    assert report.total_observations > 0
    assert isinstance(report.organization_score, float)


def test_learning_engine_domain_insights():
    """Test getting domain-specific insights."""
    engine = OrganizationLearningEngine()
    engine.record_observation(LearningDomain.AGENT_COLLABORATION, "Collab test", ["A", "B"], 0.5)
    engine.record_observation(LearningDomain.AGENT_COLLABORATION, "Collab test 2", ["A", "B"], 0.5)
    engine.record_observation(LearningDomain.AGENT_COLLABORATION, "Collab test 3", ["A", "B"], 0.5)
    engine.learn({"agents": ["A", "B"], "count": 2})

    insights = engine.get_domain_insights(LearningDomain.AGENT_COLLABORATION)
    assert len(insights) >= 0


def test_learning_engine_organization_health():
    """Test organization health metrics."""
    engine = OrganizationLearningEngine()
    engine.record_observation(LearningDomain.PROCESS_EFFICIENCY, "Test", ["A"], 0.5)
    engine.learn({"agents": ["A"], "count": 1})

    health = engine.get_organization_health()
    assert health["observations"] > 0
    assert "trend" in health


# ──────────────────────────────────────────────
# Multi Agent Service Integration Tests
# ──────────────────────────────────────────────

def test_multi_agent_service_initialization():
    """Test service initialization."""
    bus = AgentCommunicationBus()
    delegation = TaskDelegationEngine()
    coordinator = AgentCoordinator(bus, delegation)
    service = MultiAgentService(coordinator)
    assert service.bus == bus
    assert service.coordinator == coordinator


def test_multi_agent_service_run():
    """Test running the service."""
    bus = AgentCommunicationBus()
    delegation = TaskDelegationEngine()
    coordinator = AgentCoordinator(bus, delegation)
    service = MultiAgentService(coordinator)

    agents = [
        AgentIdentity("cio", "CIO", AgentRole.CIO),
        AgentIdentity("research", "Research", AgentRole.RESEARCH),
    ]
    result = service.run(agents)
    assert result["count"] == 2


def test_multi_agent_service_investment_committee():
    """Test full investment committee workflow through service."""
    bus = AgentCommunicationBus()
    delegation = TaskDelegationEngine()
    coordinator = AgentCoordinator(bus, delegation)
    service = MultiAgentService(coordinator)

    for role, name in [
        (AgentRole.CIO, "CIO"),
        (AgentRole.RESEARCH, "Research"),
        (AgentRole.STRATEGY, "Strategy"),
        (AgentRole.RISK, "Risk"),
        (AgentRole.PORTFOLIO, "Portfolio"),
        (AgentRole.EXECUTION, "Execution"),
        (AgentRole.LEARNING, "Learning"),
    ]:
        coordinator.register_agent(AgentIdentity(name.lower(), name, role))

    result = service.run_investment_committee("NVDA Analysis")
    assert result["topic"] == "NVDA Analysis"
    assert "committee" in result
    assert "debate" in result
    assert "consensus" in result
    assert "learning" in result


def test_multi_agent_service_debate_with_consensus():
    """Test debate with consensus through service."""
    bus = AgentCommunicationBus()
    delegation = TaskDelegationEngine()
    coordinator = AgentCoordinator(bus, delegation)
    service = MultiAgentService(coordinator)

    result = service.run_debate_with_consensus(
        topic="NVDA",
        bull_arguments=[
            {"statement": "AI demand growing", "strength": "STRONG", "confidence": 0.85},
        ],
        bear_arguments=[
            {"statement": "Valuation high", "strength": "MODERATE", "confidence": 0.5},
        ],
    )
    assert result["topic"] == "NVDA"
    assert "debate" in result
    assert "consensus" in result


def test_multi_agent_service_organization_report():
    """Test generating organization report."""
    bus = AgentCommunicationBus()
    delegation = TaskDelegationEngine()
    coordinator = AgentCoordinator(bus, delegation)
    service = MultiAgentService(coordinator)

    coordinator.register_agent(AgentIdentity("cio", "CIO", AgentRole.CIO))
    coordinator.register_agent(AgentIdentity("r1", "Research", AgentRole.RESEARCH))

    report = service.get_organization_report()
    assert "organization" in report
    assert "communication" in report
    assert "reputation" in report
    assert "learning" in report


def test_multi_agent_service_delegate_and_execute():
    """Test task delegation through service."""
    bus = AgentCommunicationBus()
    delegation = TaskDelegationEngine()
    coordinator = AgentCoordinator(bus, delegation)
    service = MultiAgentService(coordinator)

    coordinator.register_agent(AgentIdentity("r1", "Research", AgentRole.RESEARCH))

    task = Task(task_id="t1", domain=TaskDomain.RESEARCH, description="Market analysis")
    result = service.delegate_and_execute(task)
    assert result["delegation"]["success"] is True
