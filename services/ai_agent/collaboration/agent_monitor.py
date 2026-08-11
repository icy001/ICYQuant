"""Agent Monitor — real-time monitoring, heartbeat, and health tracking for all agents.

Pipeline:
    Heartbeat
        -> AgentMonitor.heartbeat() (receive periodic heartbeats)
        -> AgentMonitor.check_latency() (track response latency)
        -> AgentMonitor.check_queue_depth() (monitor pending tasks)
        -> AgentMonitor.assess_health() (evaluate agent health status)
        -> AgentMonitor.recover() (auto-recover unhealthy agents)

Monitors:
    - Heartbeat timeout detection
    - Per-agent latency tracking
    - Pending task queue depth
    - Health status changes
    - Automatic agent recovery
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Enums ──

class AgentHealthStatus(str, Enum):
    """Health status of a monitored agent."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNRESPONSIVE = "unresponsive"
    RECOVERING = "recovering"
    UNKNOWN = "unknown"


class RecoveryAction(str, Enum):
    """Action to take when an agent becomes unhealthy."""
    RESTART = "restart"
    REPLACE = "replace"
    NOTIFY = "notify"
    ISOLATE = "isolate"
    NONE = "none"


# ── Data Types ──

@dataclass
class HeartbeatRecord:
    """A single heartbeat record from an agent.

    Attributes:
        agent_id: The agent identifier.
        timestamp: When the heartbeat was received.
        latency_ms: Response latency in milliseconds.
        queue_depth: Number of pending tasks.
        status: Reported agent status.
        metadata: Optional additional information.
    """

    agent_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: float = 0.0
    queue_depth: int = 0
    status: str = "active"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentHealthRecord:
    """Health tracking record for a single agent.

    Attributes:
        agent_id: The agent identifier.
        status: Current health status.
        last_heartbeat: Timestamp of last heartbeat.
        avg_latency_ms: Rolling average latency.
        max_queue_depth: Maximum observed queue depth.
        recovery_count: Number of recovery attempts.
        status_changes: History of status transitions.
    """

    agent_id: str
    status: AgentHealthStatus = AgentHealthStatus.UNKNOWN
    last_heartbeat: Optional[datetime] = None
    avg_latency_ms: float = 0.0
    max_queue_depth: int = 0
    recovery_count: int = 0
    status_changes: List[Dict[str, Any]] = field(default_factory=list)

    def record_change(self, from_status: AgentHealthStatus, to_status: AgentHealthStatus) -> None:
        """Record a status transition.

        Args:
            from_status: Previous status.
            to_status: New status.
        """
        self.status_changes.append({
            "from": from_status.value,
            "to": to_status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        # Keep last 100 changes
        if len(self.status_changes) > 100:
            self.status_changes = self.status_changes[-100:]


# ── AgentMonitor ──

class AgentMonitor:
    """Real-time monitoring and health management for all agents.

    Tracks heartbeats, latency, queue depth, and health status for
    every agent in the collaboration system. Automatically detects
    unhealthy agents and triggers recovery actions.

    Supports:
        - Periodic heartbeat collection
        - Health assessment and status transitions
        - Automatic recovery with configurable actions
        - Latency and queue depth tracking
        - Health history and reporting

    Usage:
        monitor = AgentMonitor(heartbeat_timeout=10.0, check_interval=5.0)
        await monitor.initialize()
        monitor.start_monitoring()
        statuses = monitor.get_all_health()
    """

    def __init__(
        self,
        heartbeat_timeout: float = 10.0,
        check_interval: float = 5.0,
        recovery_enabled: bool = True,
        on_recover: Optional[Callable[[str, RecoveryAction], Awaitable[None]]] = None,
    ) -> None:
        """Initialize the agent monitor.

        Args:
            heartbeat_timeout: Seconds without heartbeat before marking unhealthy.
            check_interval: Seconds between health checks.
            recovery_enabled: Whether auto-recovery is enabled.
            on_recover: Optional callback for recovery actions.
        """
        self._heartbeat_timeout = heartbeat_timeout
        self._check_interval = check_interval
        self._recovery_enabled = recovery_enabled
        self._on_recover = on_recover

        self._agents: Dict[str, AgentHealthRecord] = {}
        self._heartbeats: Dict[str, List[HeartbeatRecord]] = {}
        self._max_heartbeats_per_agent = 100

        self._initialized: bool = False
        self._monitoring: bool = False
        self._monitor_task: Optional[asyncio.Task] = None
        logger.info(
            "AgentMonitor created (timeout=%.1fs, interval=%.1fs, recovery=%s)",
            heartbeat_timeout, check_interval, recovery_enabled,
        )

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the agent monitor."""
        if self._initialized:
            logger.warning("AgentMonitor already initialized")
            return
        self._initialized = True
        logger.info("AgentMonitor initialized")

    async def shutdown(self) -> None:
        """Shut down the agent monitor."""
        self.stop_monitoring()
        self._agents.clear()
        self._heartbeats.clear()
        self._initialized = False
        logger.info("AgentMonitor shutdown complete")

    # ── Monitoring Loop ──

    def start_monitoring(self) -> None:
        """Start the background health check loop."""
        if self._monitoring:
            logger.warning("AgentMonitor already monitoring")
            return
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("AgentMonitor monitoring started (interval=%.1fs)", self._check_interval)

    def stop_monitoring(self) -> None:
        """Stop the background health check loop."""
        self._monitoring = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
        logger.info("AgentMonitor monitoring stopped")

    async def _monitoring_loop(self) -> None:
        """Background loop that periodically checks agent health."""
        while self._monitoring:
            await self._check_all_agents()
            await asyncio.sleep(self._check_interval)

    # ── Heartbeat ──

    async def heartbeat(
        self,
        agent_id: str,
        latency_ms: float = 0.0,
        queue_depth: int = 0,
        status: str = "active",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Receive a heartbeat from an agent.

        Args:
            agent_id: The agent identifier.
            latency_ms: Response latency in milliseconds.
            queue_depth: Current task queue depth.
            status: Agent-reported status.
            metadata: Optional additional information.
        """
        record = HeartbeatRecord(
            agent_id=agent_id,
            latency_ms=latency_ms,
            queue_depth=queue_depth,
            status=status,
            metadata=metadata or {},
        )

        # Store heartbeat
        if agent_id not in self._heartbeats:
            self._heartbeats[agent_id] = []
        self._heartbeats[agent_id].append(record)
        if len(self._heartbeats[agent_id]) > self._max_heartbeats_per_agent:
            self._heartbeats[agent_id] = self._heartbeats[agent_id][-self._max_heartbeats_per_agent:]

        # Update health record
        health = self._get_or_create_health(agent_id)
        health.last_heartbeat = record.timestamp
        health.max_queue_depth = max(health.max_queue_depth, queue_depth)

        # Update rolling average latency
        recent = self._heartbeats[agent_id][-10:]
        health.avg_latency_ms = sum(h.latency_ms for h in recent) / len(recent)

        logger.debug(
            "Heartbeat received: agent=%s latency=%.1fms queue=%d",
            agent_id, latency_ms, queue_depth,
        )

    # ── Health Check ──

    async def _check_all_agents(self) -> None:
        """Check health of all tracked agents."""
        now = datetime.now(timezone.utc)

        for agent_id, health in list(self._agents.items()):
            previous_status = health.status
            new_status = self._assess_health(health, now)

            if new_status != previous_status:
                health.record_change(previous_status, new_status)
                health.status = new_status
                logger.warning(
                    "Agent %s health changed: %s -> %s",
                    agent_id, previous_status.value, new_status.value,
                )

                # Trigger recovery if needed
                if new_status in (AgentHealthStatus.UNHEALTHY, AgentHealthStatus.UNRESPONSIVE):
                    await self._trigger_recovery(agent_id, new_status)

    def _assess_health(self, health: AgentHealthRecord, now: datetime) -> AgentHealthStatus:
        """Assess the health status of an agent.

        Args:
            health: The agent health record.
            now: Current time for timeout comparison.

        Returns:
            Assessed health status.
        """
        # No heartbeat ever received
        if health.last_heartbeat is None:
            return AgentHealthStatus.UNKNOWN

        elapsed = (now - health.last_heartbeat).total_seconds()

        # Unresponsive: no heartbeat for too long
        if elapsed > self._heartbeat_timeout * 3:
            return AgentHealthStatus.UNRESPONSIVE

        # Unhealthy: missed heartbeat window
        if elapsed > self._heartbeat_timeout:
            return AgentHealthStatus.UNHEALTHY

        # Degraded: high latency or queue depth
        if health.avg_latency_ms > 5000 or health.max_queue_depth > 100:
            return AgentHealthStatus.DEGRADED

        # Recovering: was unhealthy but heartbeat restored
        if health.status == AgentHealthStatus.RECOVERING:
            if elapsed < self._heartbeat_timeout * 0.5:
                return AgentHealthStatus.RECOVERING
            return AgentHealthStatus.HEALTHY

        return AgentHealthStatus.HEALTHY

    # ── Recovery ──

    async def _trigger_recovery(self, agent_id: str, status: AgentHealthStatus) -> None:
        """Trigger recovery for an unhealthy agent.

        Args:
            agent_id: The agent identifier.
            status: Current health status.
        """
        if not self._recovery_enabled:
            logger.info("Recovery disabled for agent: %s", agent_id)
            return

        health = self._agents.get(agent_id)
        if not health:
            return

        health.recovery_count += 1
        health.status = AgentHealthStatus.RECOVERING

        action = RecoveryAction.RESTART if health.recovery_count <= 3 else RecoveryAction.ISOLATE
        logger.warning(
            "Triggering recovery for agent %s: action=%s count=%d (status=%s)",
            agent_id, action.value, health.recovery_count, status.value,
        )

        if self._on_recover:
            await self._on_recover(agent_id, action)

    # ── Registration ──

    def register_agent(self, agent_id: str) -> None:
        """Register an agent for monitoring.

        Args:
            agent_id: The agent identifier.
        """
        if agent_id not in self._agents:
            self._agents[agent_id] = AgentHealthRecord(agent_id=agent_id)
            logger.debug("Agent registered for monitoring: %s", agent_id)

    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent from monitoring.

        Args:
            agent_id: The agent identifier.
        """
        self._agents.pop(agent_id, None)
        self._heartbeats.pop(agent_id, None)
        logger.debug("Agent unregistered from monitoring: %s", agent_id)

    # ── Queries ──

    def get_health(self, agent_id: str) -> Optional[AgentHealthRecord]:
        """Get the health record for a specific agent.

        Args:
            agent_id: The agent identifier.

        Returns:
            AgentHealthRecord or None.
        """
        return self._agents.get(agent_id)

    def get_all_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status for all agents.

        Returns:
            Dict mapping agent_id to health summary.
        """
        return {
            agent_id: {
                "status": health.status.value,
                "last_heartbeat": (
                    health.last_heartbeat.isoformat()
                    if health.last_heartbeat else None
                ),
                "avg_latency_ms": round(health.avg_latency_ms, 2),
                "max_queue_depth": health.max_queue_depth,
                "recovery_count": health.recovery_count,
                "recent_changes": health.status_changes[-5:],
            }
            for agent_id, health in self._agents.items()
        }

    def get_heartbeats(self, agent_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent heartbeats for an agent.

        Args:
            agent_id: The agent identifier.
            limit: Maximum records to return.

        Returns:
            List of heartbeat records.
        """
        records = self._heartbeats.get(agent_id, [])[-limit:]
        return [
            {
                "timestamp": r.timestamp.isoformat(),
                "latency_ms": round(r.latency_ms, 2),
                "queue_depth": r.queue_depth,
                "status": r.status,
                "metadata": r.metadata,
            }
            for r in records
        ]

    def get_unhealthy_agents(self) -> List[str]:
        """Get list of unhealthy agent IDs.

        Returns:
            List of agent IDs with unhealthy status.
        """
        return [
            agent_id
            for agent_id, health in self._agents.items()
            if health.status
            in (AgentHealthStatus.UNHEALTHY, AgentHealthStatus.UNRESPONSIVE)
        ]

    @property
    def monitored_count(self) -> int:
        """Return the number of monitored agents."""
        return len(self._agents)

    # ── Helpers ──

    def _get_or_create_health(self, agent_id: str) -> AgentHealthRecord:
        """Get or create a health record for an agent.

        Args:
            agent_id: The agent identifier.

        Returns:
            The agent's health record.
        """
        if agent_id not in self._agents:
            self._agents[agent_id] = AgentHealthRecord(agent_id=agent_id)
        return self._agents[agent_id]

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the monitor state.

        Returns:
            Dict with monitoring status and counts.
        """
        total = len(self._agents)
        healthy = sum(
            1 for h in self._agents.values()
            if h.status == AgentHealthStatus.HEALTHY
        )
        unhealthy = len(self.get_unhealthy_agents())
        degraded = sum(
            1 for h in self._agents.values()
            if h.status == AgentHealthStatus.DEGRADED
        )
        return {
            "initialized": self._initialized,
            "monitoring": self._monitoring,
            "total_agents": total,
            "healthy": healthy,
            "unhealthy": unhealthy,
            "degraded": degraded,
            "recovery_enabled": self._recovery_enabled,
            "heartbeat_timeout_sec": self._heartbeat_timeout,
            "check_interval_sec": self._check_interval,
        }
