"""
Strategy Directory — Hierarchical strategy organization and navigation.

Provides directory-based organization for strategies with nested
grouping, filtering, and path-based access.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class DirectoryFilter:
    """Directory listing filter criteria."""
    group: Optional[str] = None
    asset_class: Optional[str] = None
    owner: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[list[str]] = None
    include_children: bool = True


@dataclass
class DirectoryEntry:
    """A single entry in the strategy directory."""
    strategy_id: str
    name: str
    path: str  # Hierarchical path, e.g., "/equity/us/momentum"
    group: str = ""
    asset_class: str = ""
    owner: str = ""
    status: str = "registered"
    version: str = "0.1.0"
    tags: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)  # Sub-strategy IDs
    parent: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class StrategyDirectory:
    """
    Hierarchical strategy organization and navigation.

    Organizes strategies in a directory structure with grouping,
    path-based access, and cross-referencing capabilities.

    Usage::

        sd = StrategyDirectory()
        await sd.initialize()
        await sd.add_entry(DirectoryEntry(
            strategy_id="strat_001", name="US Momentum",
            path="/equity/us/momentum", group="equity",
        ))
        entries = await sd.list_by_path("/equity/us")
    """

    def __init__(self) -> None:
        self._entries: dict[str, DirectoryEntry] = {}
        self._path_index: dict[str, list[str]] = {}  # path -> [strategy_ids]
        self._group_index: dict[str, list[str]] = {}  # group -> [strategy_ids]
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the strategy directory."""
        logger.info("StrategyDirectory initialized.")

    async def stop(self) -> None:
        """Stop the strategy directory."""
        logger.info("StrategyDirectory stopped.")

    # ---- Entry Management ----

    async def add_entry(self, entry: DirectoryEntry) -> DirectoryEntry:
        """Add a strategy to the directory."""
        async with self._lock:
            if entry.strategy_id in self._entries:
                raise ValueError(f"Entry already exists: {entry.strategy_id}")

            self._entries[entry.strategy_id] = entry

            # Index by path
            path = entry.path
            if path not in self._path_index:
                self._path_index[path] = []
            self._path_index[path].append(entry.strategy_id)

            # Index by group
            if entry.group:
                if entry.group not in self._group_index:
                    self._group_index[entry.group] = []
                self._group_index[entry.group].append(entry.strategy_id)

            # Update parent's children
            if entry.parent and entry.parent in self._entries:
                parent = self._entries[entry.parent]
                if entry.strategy_id not in parent.children:
                    parent.children.append(entry.strategy_id)

        logger.info(f"Directory entry added: {entry.strategy_id} at {entry.path}")
        return entry

    async def remove_entry(self, strategy_id: str) -> bool:
        """Remove a strategy from the directory."""
        async with self._lock:
            entry = self._entries.pop(strategy_id, None)
            if not entry:
                return False

            # Clean up indices
            if entry.path in self._path_index:
                self._path_index[entry.path] = [
                    sid for sid in self._path_index[entry.path] if sid != strategy_id
                ]
            if entry.group in self._group_index:
                self._group_index[entry.group] = [
                    sid for sid in self._group_index[entry.group] if sid != strategy_id
                ]
            if entry.parent and entry.parent in self._entries:
                parent = self._entries[entry.parent]
                if strategy_id in parent.children:
                    parent.children.remove(strategy_id)

        logger.info(f"Directory entry removed: {strategy_id}")
        return True

    async def get_entry(self, strategy_id: str) -> Optional[DirectoryEntry]:
        """Get a directory entry by strategy ID."""
        return self._entries.get(strategy_id)

    # ---- Listing ----

    async def list_by_path(self, path: str) -> list[DirectoryEntry]:
        """List all strategies at a given path or sub-path."""
        results = []
        for p, strategy_ids in self._path_index.items():
            if p == path or p.startswith(path + "/"):
                for sid in strategy_ids:
                    entry = self._entries.get(sid)
                    if entry:
                        results.append(entry)
        return results

    async def list_by_group(self, group: str) -> list[DirectoryEntry]:
        """List all strategies in a group."""
        strategy_ids = self._group_index.get(group, [])
        return [self._entries[sid] for sid in strategy_ids if sid in self._entries]

    async def list_groups(self) -> list[str]:
        """List all groups in the directory."""
        return sorted(self._group_index.keys())

    async def list_paths(self) -> list[str]:
        """List all paths in the directory."""
        return sorted(self._path_index.keys())

    async def list_all(self, filter_obj: Optional[DirectoryFilter] = None) -> list[DirectoryEntry]:
        """List all entries, optionally filtered."""
        results = list(self._entries.values())

        if not filter_obj:
            return results

        if filter_obj.group:
            results = [e for e in results if e.group == filter_obj.group]
        if filter_obj.asset_class:
            results = [e for e in results if e.asset_class == filter_obj.asset_class]
        if filter_obj.owner:
            results = [e for e in results if e.owner == filter_obj.owner]
        if filter_obj.status:
            results = [e for e in results if e.status == filter_obj.status]
        if filter_obj.tags:
            results = [e for e in results if any(t in e.tags for t in filter_obj.tags)]

        return results

    async def get_children(self, strategy_id: str) -> list[DirectoryEntry]:
        """Get child strategies for a parent."""
        entry = self._entries.get(strategy_id)
        if not entry:
            return []
        return [self._entries[cid] for cid in entry.children if cid in self._entries]

    async def get_parent(self, strategy_id: str) -> Optional[DirectoryEntry]:
        """Get the parent strategy."""
        entry = self._entries.get(strategy_id)
        if not entry or not entry.parent:
            return None
        return self._entries.get(entry.parent)
