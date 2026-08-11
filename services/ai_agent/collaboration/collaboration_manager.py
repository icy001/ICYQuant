"""Collaboration Manager — lifecycle coordinator for the entire multi-agent collaboration subsystem.

Pipeline:
    CollaborationManager.initialize()
        -> CollaborationRuntime (bootstrap)
        -> AgentRegistry + AgentDirectory (register agents)
        -> MessageBus + EventBridge (start communication)
        -> SharedMemory + Blackboard (initialize context)
        -> CoordinatorAgent (ready for orchestration)
        -> AgentMonitor (start supervision)
        -> CollaborationManager.shutdown() (graceful teardown)

Responsible for initializing and shutting down all collaboration components in correct
dependency order, providing a single entry-point for the multi-agent framework.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from services.ai_agent.collaboration.collaboration_runtime import (
    CollaborationRuntime,
    RuntimeConfig,
)
from services.ai_agent.collaboration.agent_registry import AgentRegistry
from services.ai_agent.collaboration.agent_directory import AgentDirectory
from services.ai_agent.collaboration.agent_discovery import AgentDiscovery
from services.ai_agent.collaboration.agent_router import AgentRouter
from services.ai_agent.collaboration.agent_scheduler import AgentScheduler
from services.ai_agent.collaboration.agent_dispatcher import AgentDispatcher
from services.ai_agent.collaboration.coordinator_agent import CoordinatorAgent
from services.ai_agent.collaboration.message_bus import MessageBus
from services.ai_agent.collaboration.message_router import MessageRouter
from services.ai_agent.collaboration.message_queue import MessageQueue
from services.ai_agent.collaboration.event_bridge import EventBridge
from services.ai_agent.collaboration.shared_memory import SharedMemory
from services.ai_agent.collaboration.blackboard import Blackboard
from services.ai_agent.collaboration.consensus_engine import ConsensusEngine
from services.ai_agent.collaboration.voting_engine import VotingEngine
from services.ai_agent.collaboration.conflict_resolver import ConflictResolver
from services.ai_agent.collaboration.negotiation_engine import NegotiationEngine
from services.ai_agent.collaboration.agent_monitor import AgentMonitor
from services.ai_agent.collaboration.agent_health import AgentHealthChecker
from services.ai_agent.collaboration.agent_metrics import AgentMetrics

logger = logging.getLogger(__name__)


class CollaborationManager:
    """Lifecycle coordinator for the entire multi-agent collaboration subsystem.

    Initializes and manages all collaboration components in correct dependency order.
    Acts as the single entry-point for the multi-agent framework.

    Supports:
        - Ordered initialization of all subsystems
        - Graceful shutdown with resource cleanup
        - Component health aggregation
        - Runtime configuration management

    Usage:
        mgr = CollaborationManager()
        await mgr.initialize()
        mgr.coordinator.assign(...)
        await mgr.shutdown()
    """

    def __init__(self) -> None:
        """Initialize the collaboration manager with all sub-components."""
        self._initialized: bool = False

        # ── Runtime ──
        self._runtime: Optional[CollaborationRuntime] = None
        self._config: Optional[RuntimeConfig] = None

        # ── Agent Management ──
        self._agent_registry: Optional[AgentRegistry] = None
        self._agent_directory: Optional[AgentDirectory] = None
        self._agent_discovery: Optional[AgentDiscovery] = None
        self._agent_router: Optional[AgentRouter] = None
        self._agent_scheduler: Optional[AgentScheduler] = None
        self._agent_dispatcher: Optional[AgentDispatcher] = None

        # ── Messaging ──
        self._message_bus: Optional[MessageBus] = None
        self._message_router: Optional[MessageRouter] = None
        self._message_queue: Optional[MessageQueue] = None
        self._event_bridge: Optional[EventBridge] = None

        # ── Context ──
        self._shared_memory: Optional[SharedMemory] = None
        self._blackboard: Optional[Blackboard] = None

        # ── Decision ──
        self._consensus_engine: Optional[ConsensusEngine] = None
        self._voting_engine: Optional[VotingEngine] = None
        self._conflict_resolver: Optional[ConflictResolver] = None
        self._negotiation_engine: Optional[NegotiationEngine] = None

        # ── Orchestration ──
        self._coordinator: Optional[CoordinatorAgent] = None

        # ── Monitor ──
        self._monitor: Optional[AgentMonitor] = None
        self._health_checker: Optional[AgentHealthChecker] = None
        self._metrics: Optional[AgentMetrics] = None

        logger.info("CollaborationManager created")

    # ── Lifecycle ──

    async def initialize(self, config: Optional[RuntimeConfig] = None) -> None:
        """Initialize all collaboration subsystems in dependency order.

        Args:
            config: Optional runtime configuration. Uses defaults if not provided.
        """
        if self._initialized:
            logger.warning("CollaborationManager already initialized")
            return

        self._config = config or RuntimeConfig()
        logger.info("Initializing CollaborationManager with config: %s", self._config)

        # Phase 1: Runtime bootstrap
        self._runtime = CollaborationRuntime(self._config)
        await self._runtime.initialize()

        # Phase 2: Agent management
        self._agent_registry = AgentRegistry()
        await self._agent_registry.initialize()
        self._agent_directory = AgentDirectory(self._agent_registry)
        await self._agent_directory.initialize()
        self._agent_discovery = AgentDiscovery(self._agent_registry, self._agent_directory)
        await self._agent_discovery.initialize()
        self._agent_router = AgentRouter(self._agent_registry, self._agent_discovery)
        await self._agent_router.initialize()
        self._agent_scheduler = AgentScheduler(self._agent_registry)
        await self._agent_scheduler.initialize()
        self._agent_dispatcher = AgentDispatcher(self._agent_router, self._agent_scheduler)
        await self._agent_dispatcher.initialize()

        # Phase 3: Messaging infrastructure
        self._message_queue = MessageQueue(self._config.max_queue_size)
        await self._message_queue.initialize()
        self._event_bridge = EventBridge(self._message_queue)
        await self._event_bridge.initialize()
        self._message_router = MessageRouter()
        await self._message_router.initialize()
        self._message_bus = MessageBus(
            self._message_queue, self._message_router, self._event_bridge,
        )
        await self._message_bus.initialize()

        # Phase 4: Shared context
        self._shared_memory = SharedMemory(self._message_bus)
        await self._shared_memory.initialize()
        self._blackboard = Blackboard(self._shared_memory)
        await self._blackboard.initialize()

        # Phase 5: Decision system
        self._voting_engine = VotingEngine()
        await self._voting_engine.initialize()
        self._conflict_resolver = ConflictResolver()
        await self._conflict_resolver.initialize()
        self._negotiation_engine = NegotiationEngine(self._message_bus)
        await self._negotiation_engine.initialize()
        self._consensus_engine = ConsensusEngine(
            self._voting_engine, self._conflict_resolver, self._negotiation_engine,
        )
        await self._consensus_engine.initialize()

        # Phase 6: Coordinator
        self._coordinator = CoordinatorAgent(
            registry=self._agent_registry,
            discovery=self._agent_discovery,
            router=self._agent_router,
            scheduler=self._agent_scheduler,
            dispatcher=self._agent_dispatcher,
            message_bus=self._message_bus,
            shared_memory=self._shared_memory,
            blackboard=self._blackboard,
            consensus_engine=self._consensus_engine,
        )
        await self._coordinator.initialize()

        # Phase 7: Monitoring
        self._health_checker = AgentHealthChecker(self._agent_registry)
        await self._health_checker.initialize()
        self._metrics = AgentMetrics()
        await self._metrics.initialize()
        self._monitor = AgentMonitor(
            self._agent_registry, self._health_checker, self._metrics,
        )
        await self._monitor.initialize()

        self._initialized = True
        logger.info("CollaborationManager initialized successfully")

    async def shutdown(self) -> None:
        """Shut down all collaboration subsystems in reverse dependency order."""
        if not self._initialized:
            logger.warning("CollaborationManager not initialized")
            return

        logger.info("Shutting down CollaborationManager...")

        # Phase 7: Stop monitoring first
        if self._monitor:
            await self._monitor.shutdown()
        if self._metrics:
            await self._metrics.shutdown()
        if self._health_checker:
            await self._health_checker.shutdown()

        # Phase 6: Stop coordinator
        if self._coordinator:
            await self._coordinator.shutdown()

        # Phase 5: Stop decision system
        if self._consensus_engine:
            await self._consensus_engine.shutdown()
        if self._negotiation_engine:
            await self._negotiation_engine.shutdown()
        if self._conflict_resolver:
            await self._conflict_resolver.shutdown()
        if self._voting_engine:
            await self._voting_engine.shutdown()

        # Phase 4: Clear context
        if self._blackboard:
            await self._blackboard.shutdown()
        if self._shared_memory:
            await self._shared_memory.shutdown()

        # Phase 3: Stop messaging
        if self._message_bus:
            await self._message_bus.shutdown()
        if self._message_router:
            await self._message_router.shutdown()
        if self._event_bridge:
            await self._event_bridge.shutdown()
        if self._message_queue:
            await self._message_queue.shutdown()

        # Phase 2: Stop agent management
        if self._agent_dispatcher:
            await self._agent_dispatcher.shutdown()
        if self._agent_scheduler:
            await self._agent_scheduler.shutdown()
        if self._agent_router:
            await self._agent_router.shutdown()
        if self._agent_discovery:
            await self._agent_discovery.shutdown()
        if self._agent_directory:
            await self._agent_directory.shutdown()
        if self._agent_registry:
            await self._agent_registry.shutdown()

        # Phase 1: Stop runtime
        if self._runtime:
            await self._runtime.shutdown()

        self._initialized = False
        logger.info("CollaborationManager shutdown complete")

    # ── Accessors ──

    @property
    def coordinator(self) -> Optional[CoordinatorAgent]:
        """Return the coordinator agent."""
        return self._coordinator

    @property
    def message_bus(self) -> Optional[MessageBus]:
        """Return the message bus."""
        return self._message_bus

    @property
    def shared_memory(self) -> Optional[SharedMemory]:
        """Return the shared memory."""
        return self._shared_memory

    @property
    def blackboard(self) -> Optional[Blackboard]:
        """Return the blackboard."""
        return self._blackboard

    @property
    def agent_registry(self) -> Optional[AgentRegistry]:
        """Return the agent registry."""
        return self._agent_registry

    @property
    def agent_discovery(self) -> Optional[AgentDiscovery]:
        """Return the agent discovery."""
        return self._agent_discovery

    @property
    def consensus_engine(self) -> Optional[ConsensusEngine]:
        """Return the consensus engine."""
        return self._consensus_engine

    @property
    def monitor(self) -> Optional[AgentMonitor]:
        """Return the agent monitor."""
        return self._monitor

    @property
    def metrics(self) -> Optional[AgentMetrics]:
        """Return the agent metrics."""
        return self._metrics

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the collaboration manager state.

        Returns:
            Dict with initialization status and component counts.
        """
        return {
            "initialized": self._initialized,
            "config": self._config.to_dict() if self._config else None,
            "agents_registered": self._agent_registry.count if self._agent_registry else 0,
            "message_queue_depth": self._message_queue.depth if self._message_queue else 0,
            "shared_memory_segments": self._shared_memory.count if self._shared_memory else 0,
            "blackboard_entries": self._blackboard.count if self._blackboard else 0,
            "monitor_active": self._monitor.is_running if self._monitor else False,
        }
