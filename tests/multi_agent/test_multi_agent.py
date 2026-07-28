"""Tests for Institutional Multi-Agent Collaboration Engine."""

from services.multi_agent import (
    Agent,
    AgentMemory,
    AgentMessageBus,
    AgentOrchestrator,
    AgentPerformanceEvaluator,
    AgentRegistry,
    HumanApproval,
    MultiAgentService,
    SharedContextManager,
    TaskPlanner,
)


def test_agent_registry():
    registry = AgentRegistry()
    agent = Agent(
        id="risk",
        role="risk",
        capability=["var"],
    )
    registry.register(agent)
    assert registry.get("risk") == agent


def test_agent_registry_missing():
    registry = AgentRegistry()
    assert registry.get("nonexistent") is None


def test_task_planner():
    planner = TaskPlanner()
    tasks = planner.plan("analyze NVIDIA")
    assert tasks == ["research", "risk", "strategy"]


def test_agent_message_bus():
    bus = AgentMessageBus()
    msg = {"sender": "risk_agent", "receiver": "strategy_agent", "message": "risk too high"}
    bus.send(msg)
    assert len(bus.messages) == 1
    assert bus.messages[0] == msg


def test_shared_context_manager():
    ctx = SharedContextManager()
    ctx.update("market", "bullish")
    assert ctx.context["market"] == "bullish"


def test_agent_memory():
    mem = AgentMemory()
    mem.save({"task": "risk assessment", "result": "low"})
    assert len(mem.records) == 1


def test_agent_performance_evaluator():
    evaluator = AgentPerformanceEvaluator()
    result = evaluator.evaluate({})
    assert result == {"score": 1.0}


def test_human_approval():
    ha = HumanApproval()
    assert ha.approve({"decision": "buy"}) is True


def test_agent_orchestrator():
    orchestrator = AgentOrchestrator()
    result = orchestrator.execute(["research", "risk"])
    assert result == {"tasks": ["research", "risk"], "status": "completed"}


def test_multi_agent_service():
    orchestrator = AgentOrchestrator()
    service = MultiAgentService(orchestrator)
    result = service.run(["research", "risk", "strategy"])
    assert result == {
        "tasks": ["research", "risk", "strategy"],
        "status": "completed",
    }
