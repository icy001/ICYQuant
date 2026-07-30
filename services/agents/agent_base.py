"""Agent Base - unified Agent framework for all ICYQuant agents.

Defines the standard agent lifecycle:
    Observe -> Analyze -> Decide -> Act -> Learn

All agents inherit from this base class with:
- Standardized lifecycle management
- Built-in communication via AgentCommunicator
- Built-in memory via AgentMemory
- Task execution support
- State reporting
"""

import time
import uuid
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .communication import AgentCommunicator
from .memory import AgentMemory, MemoryImportance

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent operational status."""

    INIT = "init"
    IDLE = "idle"
    OBSERVING = "observing"
    ANALYZING = "analyzing"
    DECIDING = "deciding"
    ACTING = "acting"
    LEARNING = "learning"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class DecisionAction(Enum):
    """Possible decision actions."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    INCREASE = "INCREASE"
    REBALANCE = "REBALANCE"
    WAIT = "WAIT"
    EXIT = "EXIT"


@dataclass
class Observation:
    """An observation made by an agent."""

    obs_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    source: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    confidence: float = 1.0
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "obs_id": self.obs_id,
            "source": self.source,
            "data": self.data,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            "tags": self.tags,
        }


@dataclass
class Analysis:
    """Result of agent analysis."""

    analysis_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent: str = ""
    summary: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    signals: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.5
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "agent": self.agent,
            "summary": self.summary,
            "metrics": self.metrics,
            "signals": self.signals,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


@dataclass
class Decision:
    """A decision made by an agent."""

    decision_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent: str = ""
    action: DecisionAction = DecisionAction.HOLD
    symbol: str = ""
    size: float = 0.0  # percentage of portfolio
    confidence: float = 0.5
    reason: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    status: str = "pending"  # pending, approved, rejected, executed
    approved_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "agent": self.agent,
            "action": self.action.value,
            "symbol": self.symbol,
            "size": self.size,
            "confidence": self.confidence,
            "reason": self.reason,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "status": self.status,
        }


class BaseAgent(ABC):
    """Base class for all ICYQuant agents.

    Implements the standard Observe -> Analyze -> Decide -> Act -> Learn loop.
    """

    agent_type: str = "base"

    def __init__(self, name: str = None, config: Dict[str, Any] = None):
        self.name = name or f"{self.agent_type}_{str(uuid.uuid4())[:6]}"
        self.config = config or {}
        self.status = AgentStatus.INIT
        self.communicator = AgentCommunicator(self.name)
        self.memory = AgentMemory(self.name)
        self.created_at = time.time()
        self.last_tick = time.time()

        # Message bus, task queue, state store set by runtime
        self.message_bus = None
        self.task_queue = None
        self.state_store = None

        # Execution history
        self._observations: List[Observation] = []
        self._analyses: List[Analysis] = []
        self._decisions: List[Decision] = []
        self._max_history = 1000

        logger.info("Agent [%s] initialized (%s)", self.name, self.agent_type)

    # ── Lifecycle ───────────────────────────────────────────────

    def start(self) -> None:
        """Start the agent."""
        self.status = AgentStatus.IDLE
        if self.state_store:
            from infrastructure.agents.state_store import AgentLifecycle
            self.state_store.update_lifecycle(self.name, AgentLifecycle.RUNNING)
        logger.info("Agent [%s] started", self.name)

    def stop(self) -> None:
        """Stop the agent."""
        self.status = AgentStatus.STOPPED
        if self.state_store:
            from infrastructure.agents.state_store import AgentLifecycle
            self.state_store.update_lifecycle(self.name, AgentLifecycle.STOPPED)
        logger.info("Agent [%s] stopped", self.name)

    def pause(self) -> None:
        """Pause the agent."""
        self.status = AgentStatus.PAUSED
        if self.state_store:
            from infrastructure.agents.state_store import AgentLifecycle
            self.state_store.update_lifecycle(self.name, AgentLifecycle.PAUSED)

    def resume(self) -> None:
        """Resume the agent."""
        self.status = AgentStatus.IDLE

    def heartbeat(self) -> None:
        """Record heartbeat."""
        if self.state_store:
            self.state_store.heartbeat(self.name)

    # ── Main Agent Loop ─────────────────────────────────────────

    def tick(self) -> Optional[Decision]:
        """Execute one full agent loop: Observe -> Analyze -> Decide -> Act -> Learn."""
        if self.status in (AgentStatus.PAUSED, AgentStatus.STOPPED, AgentStatus.ERROR):
            return None

        try:
            # 1. Observe
            self.status = AgentStatus.OBSERVING
            observation = self.observe()
            if observation:
                self._add_observation(observation)

            # 2. Analyze
            self.status = AgentStatus.ANALYZING
            analysis = self.analyze(observation)
            if analysis:
                self._add_analysis(analysis)

            # 3. Decide
            self.status = AgentStatus.DECIDING
            decision = self.decide(analysis)
            if decision:
                self._add_decision(decision)

            # 4. Act
            self.status = AgentStatus.ACTING
            self.act(decision)

            # 5. Learn
            self.status = AgentStatus.LEARNING
            self.learn(observation, analysis, decision)

            self.status = AgentStatus.IDLE
            self.last_tick = time.time()
            return decision

        except Exception as e:
            self.status = AgentStatus.ERROR
            logger.exception("Agent [%s] tick error: %s", self.name, e)
            return None

    # ── Abstract Methods ────────────────────────────────────────

    @abstractmethod
    def observe(self) -> Optional[Observation]:
        """Observe the environment and gather data."""

    @abstractmethod
    def analyze(self, observation: Optional[Observation]) -> Optional[Analysis]:
        """Analyze observations and generate insights."""

    @abstractmethod
    def decide(self, analysis: Optional[Analysis]) -> Optional[Decision]:
        """Make a decision based on analysis."""

    def act(self, decision: Optional[Decision]) -> None:
        """Execute the decision. Override for custom behavior."""
        if decision:
            logger.info("[%s] Acting: %s %s (%.1f%%, confidence=%.2f)",
                        self.name, decision.action.value, decision.symbol,
                        decision.size, decision.confidence)

    def learn(
        self,
        observation: Optional[Observation],
        analysis: Optional[Analysis],
        decision: Optional[Decision],
    ) -> None:
        """Learn from the cycle. Override for custom behavior."""
        if decision and decision.status in ("approved", "rejected"):
            outcome = decision.status
            reward = 0.5 if outcome == "approved" else -0.5
            self.memory.learn_from_outcome(
                decision=decision.to_dict(),
                outcome=outcome,
                reward=reward,
                context={
                    "observation": observation.to_dict() if observation else None,
                    "analysis": analysis.to_dict() if analysis else None,
                },
            )

    # ── Communication ───────────────────────────────────────────

    def handle_message(self, msg: Any) -> None:
        """Handle an incoming message. Override for custom handling."""
        logger.debug("[%s] Received: %s from %s", self.name, msg.event, msg.sender)

    def send_to(
        self, recipient: str, event: str, data: Dict[str, Any]
    ) -> str:
        """Send a message to another agent."""
        return self.communicator.send(recipient, event, data)

    def broadcast(self, event: str, data: Dict[str, Any]) -> str:
        """Broadcast to all agents."""
        return self.communicator.broadcast(event, data)

    # ── History Management ──────────────────────────────────────

    def _add_observation(self, obs: Observation) -> None:
        self._observations.append(obs)
        if len(self._observations) > self._max_history:
            self._observations = self._observations[-self._max_history:]

    def _add_analysis(self, analysis: Analysis) -> None:
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_history:
            self._analyses = self._analyses[-self._max_history:]

    def _add_decision(self, decision: Decision) -> None:
        self._decisions.append(decision)
        if len(self._decisions) > self._max_history:
            self._decisions = self._decisions[-self._max_history:]

    # ── Query Methods ───────────────────────────────────────────

    def get_recent_observations(self, n: int = 10) -> List[Observation]:
        return self._observations[-n:]

    def get_recent_analyses(self, n: int = 10) -> List[Analysis]:
        return self._analyses[-n:]

    def get_recent_decisions(self, n: int = 10) -> List[Decision]:
        return self._decisions[-n:]

    def get_status_report(self) -> Dict[str, Any]:
        """Get a comprehensive status report."""
        return {
            "agent_name": self.name,
            "agent_type": self.agent_type,
            "status": self.status.value,
            "uptime": time.time() - self.created_at,
            "last_tick": self.last_tick,
            "observations": len(self._observations),
            "analyses": len(self._analyses),
            "decisions": len(self._decisions),
            "memory": self.memory.get_stats(),
            "communication": self.communicator.get_stats(),
            "config": self.config,
        }

    def execute_task(self, task: Any) -> Any:
        """Execute a task from the task queue."""
        logger.debug("[%s] Executing task: %s", self.name, task.name)
        return {"status": "completed", "agent": self.name}
