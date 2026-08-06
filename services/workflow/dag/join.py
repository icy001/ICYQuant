"""
Join — synchronization point that waits for multiple parallel branches to complete.

Supports:
- ALL: wait for all branches
- ANY: proceed when any branch completes
- QUORUM: wait for N of M branches (reserved)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class JoinMode(str, Enum):
    """Join synchronization modes."""
    ALL = "all"         # Wait for all branches
    ANY = "any"         # Proceed when any branch completes
    QUORUM = "quorum"   # Wait for N of M branches


@dataclass
class JoinDefinition:
    """Definition of a join node."""

    join_id: str
    source_branches: List[str]  # Branch node IDs to wait for
    mode: JoinMode = JoinMode.ALL
    quorum_count: int = 0       # Required for QUORUM mode
    timeout_seconds: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JoinResult:
    """Result of a join operation."""

    join_id: str
    completed_branches: List[str]
    pending_branches: List[str]
    timed_out: bool = False
    results: Dict[str, Any] = field(default_factory=dict)


class JoinExecutor:
    """
    Executes a join (fan-in) operation.

    Synchronizes multiple parallel branches, collecting results
    before allowing execution to continue.
    """

    def __init__(self):
        self._pending_joins: Dict[str, asyncio.Event] = {}

    async def join(
        self,
        join_def: JoinDefinition,
        branch_states: Dict[str, str],
        branch_results: Dict[str, Any],
    ) -> JoinResult:
        """
        Wait for the join condition to be satisfied.

        Args:
            join_def: The join definition.
            branch_states: Current state of each branch (completed/failed/running).
            branch_results: Results from completed branches.

        Returns:
            JoinResult with completed and pending branches.
        """
        completed = [
            bid for bid in join_def.source_branches
            if branch_states.get(bid) in ("completed", "failed")
        ]
        pending = [
            bid for bid in join_def.source_branches
            if bid not in completed
        ]

        if join_def.mode == JoinMode.ALL:
            return JoinResult(
                join_id=join_def.join_id,
                completed_branches=completed,
                pending_branches=pending,
                results={
                    bid: branch_results.get(bid)
                    for bid in completed
                },
            )

        elif join_def.mode == JoinMode.ANY:
            if completed:
                return JoinResult(
                    join_id=join_def.join_id,
                    completed_branches=completed,
                    pending_branches=pending,
                    results={
                        bid: branch_results.get(bid)
                        for bid in completed
                    },
                )
            return JoinResult(
                join_id=join_def.join_id,
                completed_branches=[],
                pending_branches=pending,
            )

        elif join_def.mode == JoinMode.QUORUM:
            quorum = join_def.quorum_count or max(1, len(join_def.source_branches) // 2 + 1)
            if len(completed) >= quorum:
                return JoinResult(
                    join_id=join_def.join_id,
                    completed_branches=completed,
                    pending_branches=pending,
                    results={
                        bid: branch_results.get(bid)
                        for bid in completed
                    },
                )
            return JoinResult(
                join_id=join_def.join_id,
                completed_branches=completed,
                pending_branches=pending,
            )

        return JoinResult(
            join_id=join_def.join_id,
            completed_branches=completed,
            pending_branches=pending,
        )

    def is_satisfied(
        self,
        join_def: JoinDefinition,
        completed_count: int,
        total_count: int,
    ) -> bool:
        """Check if the join condition is satisfied."""
        if join_def.mode == JoinMode.ALL:
            return completed_count >= total_count
        elif join_def.mode == JoinMode.ANY:
            return completed_count >= 1
        elif join_def.mode == JoinMode.QUORUM:
            quorum = join_def.quorum_count or max(1, total_count // 2 + 1)
            return completed_count >= quorum
        return False
