"""Agent Discovery — intelligent agent discovery with capability, semantic, and tag-based matching.

Pipeline:
    DiscoveryQuery (task description + required capabilities)
        -> capability_match (exact capability matching)
        -> keyword_match (name/description/tag keyword search)
        -> semantic_match (domain and role inference)
        -> rank_results (relevance + health + performance scoring)
        -> DiscoveryResult (ranked agent list)

Supports multi-strategy discovery with fallback: capability → keyword → semantic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.ai_agent.collaboration.agent_registry import (
    AgentRegistration,
    AgentRegistry,
    AgentStatus,
)
from services.ai_agent.collaboration.agent_directory import AgentDirectory

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryQuery:
    """A query for discovering agents matching a task.

    Attributes:
        task_description: Natural language description of the task.
        required_capabilities: Required capability tags.
        preferred_roles: Preferred agent roles (in priority order).
        required_tags: Required tags.
        exclude_agents: Agent IDs to exclude from results.
        max_results: Maximum number of results to return.
    """

    task_description: str = ""
    required_capabilities: List[str] = field(default_factory=list)
    preferred_roles: List[str] = field(default_factory=list)
    required_tags: List[str] = field(default_factory=list)
    exclude_agents: List[str] = field(default_factory=list)
    max_results: int = 5


@dataclass
class DiscoveryResult:
    """Result of an agent discovery query.

    Attributes:
        agent: The discovered agent registration.
        score: Relevance score (0.0 - 1.0).
        match_reason: Human-readable reason for the match.
        match_type: How the agent was discovered (capability/keyword/semantic).
    """

    agent: AgentRegistration
    score: float = 0.0
    match_reason: str = ""
    match_type: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Return result as a dictionary."""
        return {
            "agent_id": self.agent.agent_id,
            "name": self.agent.name,
            "score": self.score,
            "match_reason": self.match_reason,
            "match_type": self.match_type,
            "capabilities": self.agent.capabilities,
            "role": self.agent.role.value,
            "status": self.agent.status.value,
        }


class AgentDiscovery:
    """Intelligent agent discovery engine with multi-strategy matching.

    Discovers the best agents for a given task using a layered matching approach:
    1. Capability match (exact capability tags)
    2. Keyword match (name, description, tags)
    3. Semantic match (domain/role inference from task description)

    Each strategy falls back to the next if insufficient results are found.

    Supports:
        - Multi-strategy discovery (capability → keyword → semantic)
        - Relevance scoring with weights
        - Health-aware filtering
        - Exclusion lists
        - Result ranking

    Usage:
        discovery = AgentDiscovery(registry, directory)
        await discovery.initialize()
        query = DiscoveryQuery(
            task_description="Analyze market volatility",
            required_capabilities=["market.analysis"],
        )
        results = await discovery.discover(query)
    """

    def __init__(self, registry: AgentRegistry, directory: AgentDirectory) -> None:
        """Initialize the discovery engine.

        Args:
            registry: Agent registry for agent lookup.
            directory: Agent directory for indexed search.
        """
        self._registry: AgentRegistry = registry
        self._directory: AgentDirectory = directory
        self._initialized: bool = False
        logger.info("AgentDiscovery created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the discovery engine."""
        if self._initialized:
            logger.warning("AgentDiscovery already initialized")
            return
        self._initialized = True
        logger.info("AgentDiscovery initialized")

    async def shutdown(self) -> None:
        """Shut down the discovery engine."""
        if not self._initialized:
            return
        self._initialized = False
        logger.info("AgentDiscovery shutdown complete")

    # ── Discovery ──

    async def discover(self, query: DiscoveryQuery) -> List[DiscoveryResult]:
        """Discover agents matching the given query.

        Uses layered matching: capability → keyword → semantic.

        Args:
            query: Discovery query with task description and requirements.

        Returns:
            Ranked list of discovery results.
        """
        if not self._initialized:
            raise RuntimeError("AgentDiscovery not initialized")

        all_results: List[DiscoveryResult] = []

        # Strategy 1: Capability match (exact)
        cap_results = self._capability_match(query)
        all_results.extend(cap_results)
        logger.debug("Capability match: %d results", len(cap_results))

        # Strategy 2: Keyword match (if not enough)
        if len(all_results) < query.max_results:
            kw_results = self._keyword_match(query, seen_ids={
                r.agent.agent_id for r in all_results
            })
            all_results.extend(kw_results)
            logger.debug("Keyword match: %d additional results", len(kw_results))

        # Strategy 3: Semantic match (if still not enough)
        if len(all_results) < query.max_results:
            sem_results = self._semantic_match(query, seen_ids={
                r.agent.agent_id for r in all_results
            })
            all_results.extend(sem_results)
            logger.debug("Semantic match: %d additional results", len(sem_results))

        # Filter out excluded agents and unavailable ones
        all_results = [
            r for r in all_results
            if r.agent.agent_id not in query.exclude_agents
            and r.agent.status != AgentStatus.UNAVAILABLE
            and r.agent.status != AgentStatus.SHUTDOWN
        ]

        # Sort by score descending
        all_results.sort(key=lambda r: r.score, reverse=True)

        # Limit results
        return all_results[:query.max_results]

    # ── Matching Strategies ──

    def _capability_match(self, query: DiscoveryQuery) -> List[DiscoveryResult]:
        """Match agents by exact capability tags.

        Args:
            query: Discovery query.

        Returns:
            Results with exact capability matches.
        """
        results: List[DiscoveryResult] = []
        if not query.required_capabilities:
            return results

        for cap in query.required_capabilities:
            agents = self._registry.list_by_capability(cap)
            for agent in agents:
                matched_caps = set(agent.capabilities) & set(query.required_capabilities)
                score = len(matched_caps) / max(len(query.required_capabilities), 1)
                results.append(DiscoveryResult(
                    agent=agent,
                    score=min(score * 1.0, 1.0),  # Capability match gets full weight
                    match_reason=f"Capability match: {', '.join(matched_caps)}",
                    match_type="capability",
                ))
        return results

    def _keyword_match(
        self, query: DiscoveryQuery, seen_ids: set,
    ) -> List[DiscoveryResult]:
        """Match agents by keyword search against names and tags.

        Args:
            query: Discovery query.
            seen_ids: Agent IDs already matched (to avoid duplicates).

        Returns:
            Additional results from keyword matching.
        """
        results: List[DiscoveryResult] = []
        entries = self._directory.search(query.task_description)
        for entry in entries:
            if entry.agent_id in seen_ids:
                continue
            agent = self._registry.lookup(entry.agent_id)
            if agent:
                results.append(DiscoveryResult(
                    agent=agent,
                    score=0.7,
                    match_reason=f"Keyword match: '{query.task_description}'",
                    match_type="keyword",
                ))
        return results

    def _semantic_match(
        self, query: DiscoveryQuery, seen_ids: set,
    ) -> List[DiscoveryResult]:
        """Match agents by domain and role inference from task description.

        Args:
            query: Discovery query.
            seen_ids: Agent IDs already matched.

        Returns:
            Additional results from semantic matching.
        """
        results: List[DiscoveryResult] = []
        task_lower = query.task_description.lower()

        # Domain keyword mapping
        domain_map = {
            "market": ["market", "price", "quote", "ticker", "volatility"],
            "research": ["research", "analyze", "backtest", "factor", "study"],
            "risk": ["risk", "var", "exposure", "drawdown", "stress"],
            "strategy": ["strategy", "signal", "alpha", "trade idea"],
            "portfolio": ["portfolio", "allocation", "rebalance", "position"],
            "execution": ["execution", "order", "trade", "fill"],
        }

        matched_domains: List[str] = []
        for domain, keywords in domain_map.items():
            if any(kw in task_lower for kw in keywords):
                matched_domains.append(domain)

        for domain in matched_domains:
            entries = self._directory.list_by_domain(domain)
            for entry in entries:
                if entry.agent_id in seen_ids:
                    continue
                agent = self._registry.lookup(entry.agent_id)
                if agent:
                    results.append(DiscoveryResult(
                        agent=agent,
                        score=0.5,
                        match_reason=f"Semantic match: domain={domain}",
                        match_type="semantic",
                    ))
        return results

    # ── Quick Discovery ──

    async def discover_by_capability(self, capability: str) -> List[DiscoveryResult]:
        """Quick discovery by single capability.

        Args:
            capability: Required capability tag.

        Returns:
            List of matching results.
        """
        query = DiscoveryQuery(required_capabilities=[capability])
        return await self.discover(query)

    async def discover_by_task(self, task_description: str) -> List[DiscoveryResult]:
        """Quick discovery by task description.

        Args:
            task_description: Natural language task description.

        Returns:
            List of matching results.
        """
        query = DiscoveryQuery(task_description=task_description)
        return await self.discover(query)

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the discovery engine state.

        Returns:
            Dict with initialization status.
        """
        return {
            "initialized": self._initialized,
        }
