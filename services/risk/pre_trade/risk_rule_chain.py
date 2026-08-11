"""
Risk Rule Chain — Pluggable chain-of-responsibility for risk checkers.

Each checker in the chain processes the order intent context and can
pass, warn, or block. Independent checkers run in parallel for low
latency; dependent rules run sequentially.

Architecture::

    Order Intent → Checker 1 → Checker 2 → ... → Checker N → Context
                   (parallel for independent rules)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from .pre_trade_context import PreTradeContext

logger = logging.getLogger(__name__)


class RiskRuleChain:
    """
    Pluggable chain of risk checkers implementing the chain-of-responsibility pattern.

    Supports:
    - Dynamic checker registration and removal
    - Hot enable/disable without restart
    - Parallel execution for independent checkers
    - Sequential execution for dependent checkers
    - Early abort on critical failures

    Usage::

        chain = RiskRuleChain()
        chain.add_checker(PositionLimitChecker())
        chain.add_checker(ExposureLimitChecker())
        chain.add_checker(MarginChecker())
        ctx = await chain.execute(context)
    """

    def __init__(self) -> None:
        self._checkers: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._stats: dict[str, int] = {
            "total_executions": 0,
            "checker_calls": 0,
            "checker_failures": 0,
            "early_aborts": 0,
        }

    @property
    def rules(self) -> list[dict[str, Any]]:
        """Return the list of registered checker metadata."""
        return [
            {"name": c["name"], "enabled": c["enabled"], "parallel": c["parallel"]}
            for c in self._checkers
        ]

    # ---- Checker Management ----

    def add_checker(
        self,
        checker: Any,
        name: Optional[str] = None,
        parallel: bool = True,
        enabled: bool = True,
        depends_on: Optional[list[str]] = None,
    ) -> None:
        """
        Register a checker in the chain.

        Args:
            checker: The checker instance (must have an async ``check(ctx)`` method).
            name: Logical name for the checker (defaults to class name).
            parallel: If True, runs in parallel with other independent checkers.
            enabled: Initial enabled state.
            depends_on: Names of checkers that must run before this one.
        """
        checker_name = name or checker.__class__.__name__
        entry = {
            "name": checker_name,
            "checker": checker,
            "parallel": parallel,
            "enabled": enabled,
            "depends_on": depends_on or [],
        }
        self._checkers.append(entry)
        logger.info(f"Checker added: {checker_name} (parallel={parallel})")

    def remove_checker(self, name: str) -> bool:
        """Remove a checker from the chain by name."""
        for i, entry in enumerate(self._checkers):
            if entry["name"] == name:
                self._checkers.pop(i)
                logger.info(f"Checker removed: {name}")
                return True
        return False

    def enable_checker(self, name: str) -> bool:
        """Enable a previously disabled checker."""
        for entry in self._checkers:
            if entry["name"] == name:
                entry["enabled"] = True
                logger.info(f"Checker enabled: {name}")
                return True
        return False

    def disable_checker(self, name: str) -> bool:
        """Disable a checker without removing it (hot-disable)."""
        for entry in self._checkers:
            if entry["name"] == name:
                entry["enabled"] = False
                logger.info(f"Checker disabled: {name}")
                return True
        return False

    # ---- Execution ----

    async def execute(self, ctx: PreTradeContext) -> PreTradeContext:
        """
        Execute all enabled checkers against the context.

        Independent (parallel=True) checkers run concurrently. Dependent
        checkers run sequentially after their dependencies. Early abort
        on critical failures if ctx.should_continue() is False.
        """
        self._stats["total_executions"] += 1

        enabled = [e for e in self._checkers if e["enabled"]]
        if not enabled:
            logger.debug("No enabled checkers; skipping rule chain.")
            return ctx

        # Partition: parallel (independent) vs sequential (has dependencies)
        parallel_checkers = [
            e for e in enabled if e["parallel"] and not e["depends_on"]
        ]
        sequential_checkers = [
            e for e in enabled if not e["parallel"] or e["depends_on"]
        ]

        # Phase 1: Run parallel (independent) checkers
        if parallel_checkers:
            tasks = []
            for entry in parallel_checkers:
                task = asyncio.create_task(
                    self._run_checker(entry, ctx),
                    name=entry["name"],
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Checker {parallel_checkers[i]['name']} failed: {result}"
                    )
                    self._stats["checker_failures"] += 1

            if not ctx.should_continue():
                self._stats["early_aborts"] += 1
                logger.warning("Early abort after parallel phase.")
                return ctx

        # Phase 2: Run sequential (dependent) checkers
        for entry in sequential_checkers:
            if not ctx.should_continue():
                self._stats["early_aborts"] += 1
                break
            try:
                await self._run_checker(entry, ctx)
            except Exception as e:
                logger.error(f"Checker {entry['name']} failed: {e}")
                self._stats["checker_failures"] += 1
                ctx.add_checker_result(
                    entry["name"], passed=False,
                    metadata={"error": str(e)},
                )

        return ctx

    async def initialize(self) -> None:
        """Initialize all registered checkers (call their initialize if available)."""
        for entry in self._checkers:
            checker = entry["checker"]
            if hasattr(checker, "initialize"):
                try:
                    await checker.initialize()
                except Exception as e:
                    logger.error(f"Failed to initialize {entry['name']}: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Return chain execution statistics."""
        stats = dict(self._stats)
        stats["checker_count"] = len(self._checkers)
        stats["enabled_count"] = sum(1 for e in self._checkers if e["enabled"])
        return stats

    # ---- Internal ----

    async def _run_checker(
        self, entry: dict[str, Any], ctx: PreTradeContext
    ) -> None:
        """Run a single checker against the context."""
        checker_name = entry["name"]
        checker = entry["checker"]

        self._stats["checker_calls"] += 1

        if hasattr(checker, "check"):
            await checker.check(ctx)
            logger.debug(f"Checker {checker_name}: completed")
        else:
            logger.warning(f"Checker {checker_name} has no check(ctx) method")
