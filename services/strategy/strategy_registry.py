"""
Production strategy registry.

Unified registration, lookup, and lifecycle tracking for all strategies
in the production strategy platform. Supports multi-tenant isolation,
version management, and capability-based discovery.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from .strategy_manifest import StrategyManifest
from .strategy_metadata import StrategyMetadata
from .strategy_state import StrategyLifecycleState
from .strategy_version import StrategyVersion, VersionEntry, VersionHistory

logger = logging.getLogger(__name__)


class StrategyRegistry:
    """Central registry for all production strategies.

    Provides:
        - Strategy registration and deregistration
        - Multi-index lookup (by name, capability, tag, state, version)
        - Version history tracking
        - Canary deployment support
        - Access control by permission scope
    """

    def __init__(self) -> None:
        # Primary storage: strategy_id → manifest
        self._strategies: Dict[str, StrategyManifest] = {}

        # Metadata: strategy_id → metadata
        self._metadata: Dict[str, StrategyMetadata] = {}

        # Version history: strategy_id → VersionHistory
        self._versions: Dict[str, VersionHistory] = {}

        # Indexes
        self._by_name: Dict[str, List[str]] = {}
        self._by_state: Dict[StrategyLifecycleState, Set[str]] = {
            s: set() for s in StrategyLifecycleState
        }
        self._by_tag: Dict[str, Set[str]] = {}
        self._by_capability: Dict[str, Set[str]] = {}

        self._initialized: bool = False

    # ── Lifecycle ──

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("StrategyRegistry initialized")

    async def shutdown(self) -> None:
        self._strategies.clear()
        self._metadata.clear()
        self._versions.clear()
        self._by_name.clear()
        for s in self._by_state:
            self._by_state[s].clear()
        self._by_tag.clear()
        self._by_capability.clear()
        self._initialized = False
        logger.info("StrategyRegistry shut down")

    # ── Registration ──

    def register(
        self,
        strategy_id: str,
        manifest: StrategyManifest,
        metadata: Optional[StrategyMetadata] = None,
    ) -> None:
        """Register a strategy with the platform."""
        if strategy_id in self._strategies:
            logger.warning("Strategy %s already registered, updating", strategy_id)

        self._strategies[strategy_id] = manifest

        # Metadata
        if metadata:
            self._metadata[strategy_id] = metadata
        else:
            self._metadata[strategy_id] = StrategyMetadata(
                strategy_id=strategy_id,
                name=manifest.name,
                version=manifest.version,
                author=manifest.author,
                description=manifest.description,
                tags=list(manifest.tags),
                capability=manifest.capability,
            )

        # Version tracking
        version = StrategyVersion.parse(manifest.version)
        version_entry = VersionEntry(
            strategy_id=strategy_id,
            version=version,
            author=manifest.author,
            is_active=True,
        )
        if strategy_id not in self._versions:
            self._versions[strategy_id] = VersionHistory(strategy_id=strategy_id)
        self._versions[strategy_id].add_version(version_entry)

        # Indexes
        self._by_name.setdefault(manifest.name, []).append(strategy_id)

        state = self._metadata[strategy_id].state
        self._by_state[state].add(strategy_id)

        for tag in manifest.tags:
            self._by_tag.setdefault(tag, set()).add(strategy_id)

        cap_key = f"{manifest.capability.style}/{manifest.capability.frequency}"
        self._by_capability.setdefault(cap_key, set()).add(strategy_id)

        logger.info(
            "Strategy registered: %s (v%s, state=%s)",
            strategy_id,
            manifest.version,
            state.value,
        )

    def unregister(self, strategy_id: str) -> None:
        """Remove a strategy from the registry."""
        manifest = self._strategies.pop(strategy_id, None)
        if manifest is None:
            logger.warning("Strategy %s not found for unregistration", strategy_id)
            return

        # Clean up indexes
        self._by_name.get(manifest.name, []).remove(strategy_id)

        metadata = self._metadata.pop(strategy_id, None)
        if metadata:
            self._by_state.get(metadata.state, set()).discard(strategy_id)

        for tag in manifest.tags:
            self._by_tag.get(tag, set()).discard(strategy_id)

        cap_key = f"{manifest.capability.style}/{manifest.capability.frequency}"
        self._by_capability.get(cap_key, set()).discard(strategy_id)

        self._versions.pop(strategy_id, None)

        logger.info("Strategy unregistered: %s", strategy_id)

    # ── State Management ──

    def update_state(
        self,
        strategy_id: str,
        new_state: StrategyLifecycleState,
        reason: str = "",
    ) -> None:
        """Update the lifecycle state of a strategy."""
        metadata = self._metadata.get(strategy_id)
        if metadata is None:
            raise KeyError(f"Strategy not found: {strategy_id}")

        old_state = metadata.state
        if old_state == new_state:
            return

        # Update state indexes
        self._by_state.get(old_state, set()).discard(strategy_id)
        self._by_state[new_state].add(strategy_id)

        # Update metadata
        metadata.add_transition(old_state, new_state, reason)
        logger.info(
            "Strategy %s state: %s → %s (%s)",
            strategy_id,
            old_state.value,
            new_state.value,
            reason,
        )

    # ── Lookup ──

    def get_manifest(self, strategy_id: str) -> Optional[StrategyManifest]:
        return self._strategies.get(strategy_id)

    def get_metadata(self, strategy_id: str) -> Optional[StrategyMetadata]:
        return self._metadata.get(strategy_id)

    def get_version_history(self, strategy_id: str) -> Optional[VersionHistory]:
        return self._versions.get(strategy_id)

    # ── Listing ──

    def list_all(self) -> List[str]:
        return list(self._strategies.keys())

    def list_by_name(self, name: str) -> List[str]:
        return list(self._by_name.get(name, []))

    def list_by_state(self, state: StrategyLifecycleState) -> List[str]:
        return list(self._by_state.get(state, set()))

    def list_active(self) -> List[str]:
        """List strategies in active (running/paused/degraded) states."""
        from .strategy_state import ACTIVE_STATES

        result: List[str] = []
        for state in ACTIVE_STATES:
            result.extend(self._by_state.get(state, set()))
        return result

    def list_by_tag(self, tag: str) -> List[str]:
        return list(self._by_tag.get(tag, set()))

    def list_by_capability(
        self,
        style: Optional[str] = None,
        frequency: Optional[str] = None,
    ) -> List[str]:
        results: Set[str] = set()
        for cap_key, ids in self._by_capability.items():
            matches = True
            if style and style not in cap_key:
                matches = False
            if frequency and frequency not in cap_key:
                matches = False
            if matches:
                results.update(ids)
        return list(results)

    def search(self, query: str) -> List[str]:
        """Full-text search across strategy names, descriptions, and tags."""
        query_lower = query.lower()
        results: Set[str] = set()
        for sid, manifest in self._strategies.items():
            if query_lower in manifest.name.lower():
                results.add(sid)
            elif query_lower in manifest.description.lower():
                results.add(sid)
            elif any(query_lower in tag.lower() for tag in manifest.tags):
                results.add(sid)
        return list(results)

    # ── Batch Operations ──

    def get_batch(self, strategy_ids: List[str]) -> Dict[str, StrategyManifest]:
        return {sid: self._strategies[sid] for sid in strategy_ids if sid in self._strategies}

    def get_batch_metadata(
        self,
        strategy_ids: List[str],
    ) -> Dict[str, StrategyMetadata]:
        return {sid: self._metadata[sid] for sid in strategy_ids if sid in self._metadata}

    # ── Summary ──

    @property
    def count(self) -> int:
        return len(self._strategies)

    @property
    def active_count(self) -> int:
        return len(self.list_active())

    def get_summary(self) -> Dict[str, Any]:
        state_counts: Dict[str, int] = {}
        for state, ids in self._by_state.items():
            if ids:
                state_counts[state.value] = len(ids)

        return {
            "total_strategies": self.count,
            "active_strategies": self.active_count,
            "state_distribution": state_counts,
            "strategies_with_versions": len(self._versions),
        }
