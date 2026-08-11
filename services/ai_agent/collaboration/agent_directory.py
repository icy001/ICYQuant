"""Agent Directory — hierarchical agent index with multi-dimensional categorization.

Pipeline:
    AgentRegistration (from AgentRegistry)
        -> AgentDirectory.initialize() (build indices)
        -> categorize (by domain / role / capability / status)
        -> search (keyword + tag + capability matching)
        -> get_tree() (hierarchical view)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.ai_agent.collaboration.agent_registry import (
    AgentRegistration,
    AgentRegistry,
    AgentRole,
    AgentStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class DirectoryEntry:
    """An entry in the agent directory with categorization metadata.

    Attributes:
        agent_id: Reference to registered agent.
        name: Agent name.
        role: Agent role.
        domain: Business domain (e.g. "market", "research", "risk").
        capabilities: Agent capabilities.
        status: Current runtime status.
        tags: Searchable tags.
        indexed_at: When this entry was indexed.
    """

    agent_id: str = ""
    name: str = ""
    role: AgentRole = AgentRole.OBSERVER
    domain: str = ""
    capabilities: List[str] = field(default_factory=list)
    status: AgentStatus = AgentStatus.REGISTERED
    tags: List[str] = field(default_factory=list)
    indexed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Return entry as a dictionary."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role.value,
            "domain": self.domain,
            "capabilities": self.capabilities,
            "status": self.status.value,
            "tags": self.tags,
            "indexed_at": self.indexed_at.isoformat(),
        }


class AgentDirectory:
    """Hierarchical index of agents with multi-dimensional categorization.

    Builds and maintains a searchable directory of all registered agents,
    organized by domain, role, capability, and status. Provides keyword,
    tag, and capability-based search.

    Supports:
        - Multi-dimensional categorization (domain, role, capability, status)
        - Keyword and tag-based search
        - Capability filtering
        - Hierarchical tree view
        - Auto-sync with AgentRegistry

    Usage:
        directory = AgentDirectory(registry)
        await directory.initialize()
        results = directory.search("market analysis")
        tree = directory.get_tree()
    """

    def __init__(self, registry: AgentRegistry) -> None:
        """Initialize the agent directory.

        Args:
            registry: The agent registry to index.
        """
        self._registry: AgentRegistry = registry
        self._entries: Dict[str, DirectoryEntry] = {}
        self._domain_index: Dict[str, List[str]] = {}
        self._tag_index: Dict[str, List[str]] = {}
        self._initialized: bool = False
        logger.info("AgentDirectory created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Build the directory indices from the registry."""
        if self._initialized:
            logger.warning("AgentDirectory already initialized")
            return
        self._rebuild_all()
        self._initialized = True
        logger.info("AgentDirectory initialized with %d entries", len(self._entries))

    async def shutdown(self) -> None:
        """Clear the directory."""
        if not self._initialized:
            return
        self._entries.clear()
        self._domain_index.clear()
        self._tag_index.clear()
        self._initialized = False
        logger.info("AgentDirectory shutdown complete")

    # ── Indexing ──

    def _rebuild_all(self) -> None:
        """Rebuild all directory indices from the registry."""
        self._entries.clear()
        self._domain_index.clear()
        self._tag_index.clear()
        for agent in self._registry.list_all():
            self._index_agent(agent)

    def _index_agent(self, agent: AgentRegistration) -> None:
        """Index a single agent into all directory structures.

        Args:
            agent: The agent registration to index.
        """
        domain = self._infer_domain(agent)
        tags = self._extract_tags(agent)

        entry = DirectoryEntry(
            agent_id=agent.agent_id,
            name=agent.name,
            role=agent.role,
            domain=domain,
            capabilities=list(agent.capabilities),
            status=agent.status,
            tags=tags,
        )
        self._entries[agent.agent_id] = entry

        # Domain index
        self._domain_index.setdefault(domain, []).append(agent.agent_id)

        # Tag index
        for tag in tags:
            self._tag_index.setdefault(tag, []).append(agent.agent_id)

    def refresh(self) -> None:
        """Refresh the directory to reflect registry changes."""
        self._rebuild_all()
        logger.debug("AgentDirectory refreshed")

    # ── Domain / Tag Inference ──

    @staticmethod
    def _infer_domain(agent: AgentRegistration) -> str:
        """Infer the business domain from agent capabilities and role.

        Args:
            agent: Agent registration.

        Returns:
            Domain string (e.g. "market", "research", "risk").
        """
        domain_keywords = {
            "market": ["market", "quote", "price"],
            "research": ["research", "backtest", "factor", "analyze"],
            "risk": ["risk", "var", "exposure", "stress"],
            "strategy": ["strategy", "signal", "alpha"],
            "portfolio": ["portfolio", "allocation", "rebalance"],
            "execution": ["execution", "order", "trade", "oms"],
            "data": ["data", "feed", "stream"],
            "reporting": ["report", "summary", "audit"],
        }
        all_text = " ".join(agent.capabilities + [agent.name, agent.role.value]).lower()
        for domain, keywords in domain_keywords.items():
            if any(kw in all_text for kw in keywords):
                return domain
        return "general"

    @staticmethod
    def _extract_tags(agent: AgentRegistration) -> List[str]:
        """Extract searchable tags from agent metadata.

        Args:
            agent: Agent registration.

        Returns:
            List of tags.
        """
        tags: List[str] = []
        tags.extend(agent.capabilities)
        tags.append(agent.role.value)
        if agent.metadata:
            extra_tags = agent.metadata.get("tags", [])
            if isinstance(extra_tags, list):
                tags.extend(extra_tags)
        return list(set(tags))

    # ── Search ──

    def search(self, query: str) -> List[DirectoryEntry]:
        """Search the directory by keyword.

        Matches against agent name, domain, capabilities, and tags.

        Args:
            query: Search keyword(s).

        Returns:
            List of matching directory entries.
        """
        query_lower = query.lower()
        results: List[DirectoryEntry] = []
        for entry in self._entries.values():
            searchable = " ".join([
                entry.name, entry.domain, entry.role.value,
                *entry.capabilities, *entry.tags,
            ]).lower()
            if query_lower in searchable:
                results.append(entry)
        return results

    def search_by_tags(self, tags: List[str]) -> List[DirectoryEntry]:
        """Search agents matching all given tags.

        Args:
            tags: Required tags.

        Returns:
            List of matching directory entries.
        """
        if not tags:
            return list(self._entries.values())
        candidate_ids = set(self._tag_index.get(tags[0], []))
        for tag in tags[1:]:
            candidate_ids &= set(self._tag_index.get(tag, []))
        return [self._entries[aid] for aid in candidate_ids if aid in self._entries]

    def list_by_domain(self, domain: str) -> List[DirectoryEntry]:
        """List agents in a specific domain.

        Args:
            domain: Business domain name.

        Returns:
            List of directory entries in that domain.
        """
        agent_ids = self._domain_index.get(domain, [])
        return [self._entries[aid] for aid in agent_ids if aid in self._entries]

    # ── Tree ──

    def get_tree(self) -> Dict[str, Any]:
        """Return a hierarchical tree view of the directory.

        Returns:
            Nested dict organized by domain -> role -> agents.
        """
        tree: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        for entry in self._entries.values():
            domain_node = tree.setdefault(entry.domain, {})
            role_node = domain_node.setdefault(entry.role.value, [])
            role_node.append({
                "agent_id": entry.agent_id,
                "name": entry.name,
                "status": entry.status.value,
                "capabilities": entry.capabilities,
            })
        return tree

    # ── Status ──

    @property
    def count(self) -> int:
        """Return the number of directory entries."""
        return len(self._entries)

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the directory state.

        Returns:
            Dict with entry counts and domain breakdown.
        """
        domain_counts: Dict[str, int] = {}
        for entry in self._entries.values():
            domain_counts[entry.domain] = domain_counts.get(entry.domain, 0) + 1

        return {
            "initialized": self._initialized,
            "total_entries": len(self._entries),
            "domains": len(self._domain_index),
            "tags": len(self._tag_index),
            "domain_breakdown": domain_counts,
        }
