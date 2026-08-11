"""Observation Engine — tool output processing and state integration.

Pipeline:
    Tool Output
        -> ObservationEngine.process()
        -> Observation (structured output, state delta, memory update)
        -> Agent Memory (Working, Short-Term, Long-Term)
        -> State Update
        -> Next Action Input
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from services.ai_agent.tooling.tool_result import ToolResult

logger = logging.getLogger(__name__)


# ── Enums ──

class ObservationType(str, Enum):
    """Type of observation."""

    TOOL_OUTPUT = "tool_output"
    STATE_CHANGE = "state_change"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    SYSTEM = "system"


# ── Observation ──

@dataclass
class Observation:
    """A structured observation from a tool execution.

    Captures tool output in a normalized format suitable for
    ingestion into Agent Memory and planning pipelines.

    Supports:
        - Structured data extraction
        - State delta tracking
        - Memory annotation
        - Context enrichment

    Usage:
        obs = Observation.from_result(tool_result)
        await memory.update(obs)
    """

    observation_id: str = ""
    observation_type: ObservationType = ObservationType.TOOL_OUTPUT

    # ── Source ──
    tool_name: str = ""
    execution_id: str = ""
    session_id: str = ""

    # ── Content ──
    summary: str = ""
    data: Any = None
    state_delta: Dict[str, Any] = field(default_factory=dict)
    key_findings: List[str] = field(default_factory=list)

    # ── Metadata ──
    importance: float = 0.5  # 0.0 to 1.0
    confidence: float = 1.0  # 0.0 to 1.0
    tags: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)

    # ── Timing ──
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Factory Methods ──

    @classmethod
    def from_result(
        cls,
        result: ToolResult,
        session_id: str = "",
    ) -> "Observation":
        """Create an observation from a tool result.

        Args:
            result: The tool execution result.
            session_id: Optional session identifier.

        Returns:
            An Observation instance.
        """
        from uuid import uuid4

        obs_type = ObservationType.TOOL_OUTPUT
        summary = ""
        importance = 0.5

        if not result.success:
            obs_type = ObservationType.ERROR
            summary = f"Tool '{result.tool_name}' failed: {result.error}"
            importance = 0.9
        else:
            summary = f"Tool '{result.tool_name}' completed in {result.latency_ms:.0f}ms"
            importance = 0.5

        return cls(
            observation_id=uuid4().hex,
            observation_type=obs_type,
            tool_name=result.tool_name,
            execution_id=result.execution_id,
            session_id=session_id,
            summary=summary,
            data=result.data,
            importance=importance,
            confidence=0.95 if result.success else 0.0,
            tags=[result.tool_name],
            context={
                "success": result.success,
                "error": result.error,
                "latency_ms": result.latency_ms,
                "from_cache": result.from_cache,
            },
        )

    @classmethod
    def state_change(
        cls,
        state_delta: Dict[str, Any],
        description: str = "",
    ) -> "Observation":
        """Create a state-change observation.

        Args:
            state_delta: The state changes.
            description: Human-readable description.

        Returns:
            An Observation instance.
        """
        from uuid import uuid4

        return cls(
            observation_id=uuid4().hex,
            observation_type=ObservationType.STATE_CHANGE,
            summary=description or f"State changed: {list(state_delta.keys())}",
            state_delta=state_delta,
            importance=0.7,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "observation_id": self.observation_id,
            "type": self.observation_type.value,
            "tool_name": self.tool_name,
            "execution_id": self.execution_id,
            "summary": self.summary,
            "data": self.data,
            "state_delta": self.state_delta,
            "key_findings": self.key_findings,
            "importance": self.importance,
            "confidence": self.confidence,
            "tags": self.tags,
            "observed_at": self.observed_at.isoformat(),
        }

    def to_memory_entry(self) -> Dict[str, Any]:
        """Convert to a memory-friendly format."""
        return {
            "type": self.observation_type.value,
            "content": self.summary,
            "data": self.data,
            "importance": self.importance,
            "tags": self.tags,
            "timestamp": self.observed_at.isoformat(),
        }


# ── ObservationEngine ──

class ObservationEngine:
    """Processes tool outputs into structured observations.

    All tool results pass through this engine to be normalized,
    enriched, and routed into Agent Memory. Provides a unified
    observation pipeline for the agent's state tracking.

    Supports:
        - Tool result -> Observation conversion
        - State delta extraction
        - Importance scoring
        - Memory routing
        - Observation history

    Usage:
        engine = ObservationEngine()
        obs = await engine.process(tool_result, session_id)
        await memory_manager.ingest(obs)
    """

    def __init__(self, max_history: int = 1000) -> None:
        """Initialize the observation engine.

        Args:
            max_history: Maximum number of observations to retain.
        """
        self._max_history = max_history
        self._history: List[Observation] = []
        self._subscribers: List[Any] = []

        self._initialized: bool = False
        logger.info(f"ObservationEngine created (max_history={max_history})")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the observation engine."""
        self._initialized = True
        logger.info("ObservationEngine initialized")

    async def shutdown(self) -> None:
        """Shutdown the observation engine."""
        self._history.clear()
        self._subscribers.clear()
        self._initialized = False
        logger.info("ObservationEngine shutdown complete")

    # ── Processing ──

    async def process(
        self,
        result: ToolResult,
        session_id: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> Observation:
        """Process a tool result into an observation.

        Args:
            result: The tool execution result.
            session_id: The current session identifier.
            context: Optional additional context.

        Returns:
            An Observation instance.
        """
        obs = Observation.from_result(result, session_id=session_id)

        if context:
            obs.context.update(context)

        # Extract key findings from successful results
        if result.success and result.data:
            obs.key_findings = self._extract_findings(result)

        # Add to history
        self._add_to_history(obs)

        # Notify subscribers
        await self._notify_subscribers(obs)

        logger.debug(f"Observation processed: {obs.observation_id} for {result.tool_name}")
        return obs

    async def process_batch(
        self,
        results: List[ToolResult],
        session_id: str = "",
    ) -> List[Observation]:
        """Process multiple tool results.

        Args:
            results: List of tool results.
            session_id: The session identifier.

        Returns:
            List of observations.
        """
        observations = []
        for result in results:
            obs = await self.process(result, session_id)
            observations.append(obs)
        return observations

    # ── Subscribers ──

    def subscribe(self, subscriber: Any) -> None:
        """Subscribe to observations.

        Args:
            subscriber: An object with async on_observation(obs) method.
        """
        self._subscribers.append(subscriber)

    def unsubscribe(self, subscriber: Any) -> None:
        """Unsubscribe from observations.

        Args:
            subscriber: The subscriber to remove.
        """
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)

    async def _notify_subscribers(self, obs: Observation) -> None:
        """Notify all subscribers of a new observation.

        Args:
            obs: The observation to publish.
        """
        for subscriber in self._subscribers:
            try:
                if hasattr(subscriber, "on_observation"):
                    await subscriber.on_observation(obs)
            except Exception as e:
                logger.error(f"Subscriber notification failed: {e}")

    # ── History ──

    def get_history(
        self,
        tool_name: Optional[str] = None,
        limit: int = 50,
    ) -> List[Observation]:
        """Get observation history.

        Args:
            tool_name: Optional tool name filter.
            limit: Maximum results.

        Returns:
            List of observations.
        """
        if tool_name:
            return [o for o in self._history if o.tool_name == tool_name][:limit]
        return self._history[-limit:]

    def _add_to_history(self, obs: Observation) -> None:
        """Add an observation to history, maintaining max size.

        Args:
            obs: The observation to add.
        """
        self._history.append(obs)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    # ── Private Methods ──

    @staticmethod
    def _extract_findings(result: ToolResult) -> List[str]:
        """Extract key findings from a successful result.

        Args:
            result: The tool result.

        Returns:
            List of finding strings.
        """
        findings: List[str] = []
        data = result.data

        if isinstance(data, dict):
            # Extract top-level scalar values as findings
            for key, value in data.items():
                if isinstance(value, (str, int, float, bool)):
                    findings.append(f"{key}: {value}")
                elif isinstance(value, list) and len(value) <= 3:
                    findings.append(f"{key}: {value}")
        elif isinstance(data, (str, int, float)):
            findings.append(str(data))

        return findings

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get observation engine status."""
        return {
            "history_size": len(self._history),
            "max_history": self._max_history,
            "subscribers": len(self._subscribers),
            "initialized": self._initialized,
        }
