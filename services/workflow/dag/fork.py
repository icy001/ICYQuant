"""
Fork — parallel fan-out node that splits execution into multiple concurrent branches.

A Fork node dispatches work to multiple child nodes simultaneously.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ForkMode(str, Enum):
    """Fork execution modes."""
    ALL = "all"            # Execute all branches (static fan-out)
    DYNAMIC = "dynamic"    # Branch count determined at runtime (reserved)
    CONDITIONAL = "conditional"  # Only execute branches that meet conditions


@dataclass
class ForkDefinition:
    """Definition of a fork node."""

    fork_id: str
    branches: List[str]          # Target node IDs for each branch
    mode: ForkMode = ForkMode.ALL
    max_concurrency: int = 0     # 0 = unlimited
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ForkResult:
    """Result of a fork operation."""

    fork_id: str
    completed_branches: List[str]
    failed_branches: List[str]
    branch_results: Dict[str, Any] = field(default_factory=dict)
    branch_errors: Dict[str, str] = field(default_factory=dict)


class ForkExecutor:
    """
    Executes a fork (parallel fan-out) operation.

    Forks execution into multiple concurrent branches, each executing independently.
    """

    def __init__(self, max_concurrency: int = 0):
        self.max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency) if max_concurrency > 0 else None

    async def fork(
        self,
        fork_def: ForkDefinition,
        branch_executor_fn: Any,
        context: Dict[str, Any],
    ) -> ForkResult:
        """
        Execute a fork: dispatch all branches in parallel.

        Args:
            fork_def: The fork definition.
            branch_executor_fn: Async function to execute each branch node.
            context: Shared execution context.

        Returns:
            ForkResult with per-branch outcomes.
        """
        if not fork_def.branches:
            return ForkResult(
                fork_id=fork_def.fork_id,
                completed_branches=[],
                failed_branches=[],
            )

        async def _run_branch(branch_id: str) -> tuple:
            if self._semaphore:
                async with self._semaphore:
                    return await self._execute_branch(branch_id, branch_executor_fn, context)
            else:
                return await self._execute_branch(branch_id, branch_executor_fn, context)

        tasks = [_run_branch(bid) for bid in fork_def.branches]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        result = ForkResult(fork_id=fork_def.fork_id)
        for i, item in enumerate(results):
            branch_id = fork_def.branches[i]
            if isinstance(item, Exception):
                result.failed_branches.append(branch_id)
                result.branch_errors[branch_id] = str(item)
            else:
                ok, output, error = item
                if ok:
                    result.completed_branches.append(branch_id)
                    result.branch_results[branch_id] = output
                else:
                    result.failed_branches.append(branch_id)
                    result.branch_errors[branch_id] = error

        return result

    async def _execute_branch(
        self,
        branch_id: str,
        executor_fn: Any,
        context: Dict[str, Any],
    ) -> tuple:
        """Execute a single branch."""
        try:
            result = await executor_fn(branch_id, context)
            return (True, result, None)
        except Exception as e:
            return (False, None, str(e))
