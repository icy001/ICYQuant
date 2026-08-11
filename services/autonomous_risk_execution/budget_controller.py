"""
Budget Controller — dynamic risk budget allocation and release.

Dynamically controls risk budgets based on market regime,
portfolio performance, and risk constraints. Provides a
centralized ledger for budget state tracking, allocation
requests, releases, and regime-driven scaling.

Core responsibilities:
    - Maintain per-portfolio budget state (base, allocated,
      used, reserved, available).
    - Accept and approve/reject budget allocation requests
      subject to current regime multipliers and policy
      limits.
    - Release previously allocated budget back to the pool.
    - Recalculate budgets across all portfolios when the
      global regime changes or a systematic rebalance is
      required.
    - Track allocation history for auditing, reporting,
      and learning.
    - Surface aggregate statistics for monitoring and
      dashboards.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class BudgetRegime(Enum):
    """Budget regimes and their default multipliers."""
    NORMAL = "NORMAL"
    TRENDING = "TRENDING"
    HIGH_VOL = "HIGH_VOL"
    RISK_OFF = "RISK_OFF"
    CRISIS = "CRISIS"


# ── Default regime multipliers ────────────────────────────────
_DEFAULT_REGIME_MULTIPLIERS: dict[str, float] = {
    "NORMAL": 1.00,
    "TRENDING": 0.90,
    "HIGH_VOL": 0.60,
    "RISK_OFF": 0.35,
    "CRISIS": 0.15,
}


@dataclass
class BudgetState:
    """
    Snapshot of a single portfolio's budget position.

    Attributes:
        portfolio_id: Unique identifier for the portfolio.
        current_budget: Effective budget after regime scaling
            and any discretionary adjustments.
        base_budget: Static budget before regime multipliers.
        regime_multiplier: Current regime multiplier applied
            to the base budget.
        available_budget: Amount available for new allocations
            (current - allocated - reserved).
        allocated_budget: Sum of active allocations that have
            not yet been released or consumed.
        used_budget: Amount of budget actually consumed by
            positions (realised risk).
        reserved_budget: Budget earmarked for pending orders
            or pending allocation approvals.
        last_updated: Timestamp of the most recent state change.
        last_change_reason: Human-readable reason for the last
            change (e.g. "regime shift", "drawdown breach").
    """

    portfolio_id: str = ""
    current_budget: float = 1.0
    base_budget: float = 1.0
    regime_multiplier: float = 1.0
    available_budget: float = 1.0
    allocated_budget: float = 0.0
    used_budget: float = 0.0
    reserved_budget: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)
    last_change_reason: str = ""


@dataclass
class BudgetAllocation:
    """
    Record of a single budget allocation request.

    Attributes:
        id: Unique identifier for the allocation record.
        portfolio_id: Portfolio that requested the allocation.
        timestamp: When the allocation was requested/processed.
        requested_pct: Percentage of budget the portfolio asked
            for (as a fraction, e.g. 0.15 = 15%).
        allocated_pct: Percentage actually allocated after
            applying regime and policy constraints.
        remaining_pct: Percentage of the request that could not
            be fulfilled (requested - allocated, floored at 0).
        reason: Context or justification provided by the
            requester.
        regime_at_time: Market regime active at the time of
            the request.
        approved: Whether the allocation was approved and
            applied.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    portfolio_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    requested_pct: float = 0.0
    allocated_pct: float = 0.0
    remaining_pct: float = 0.0
    reason: str = ""
    regime_at_time: str = "NORMAL"
    approved: bool = True


@dataclass
class BudgetStats:
    """
    Aggregate statistics across all portfolios.

    Attributes:
        total_portfolios: Number of portfolios tracked.
        avg_budget: Mean current_budget across portfolios.
        min_budget_used: Lowest used_budget observed.
        max_budget_used: Highest used_budget observed.
        total_allocations: Total number of allocation records
            in the history.
        total_releases: Total number of budget releases.
        by_regime: Per-regime breakdown of budget usage.
        utilization_rate_pct: Overall utilisation percentage
            (used / total available * 100).
    """

    total_portfolios: int = 0
    avg_budget: float = 0.0
    min_budget_used: float = 0.0
    max_budget_used: float = 0.0
    total_allocations: int = 0
    total_releases: int = 0
    by_regime: dict[str, float] = field(default_factory=dict)
    utilization_rate_pct: float = 0.0


class BudgetController:
    """
    Dynamic risk budget controller.

    The BudgetController maintains a per-portfolio ledger of
    risk budget and exposes operations to allocate, release,
    and recalibrate budget based on market regime, portfolio
    drawdown, and other constraints.

    Budget model
    ------------
        current_budget = base_budget * regime_multiplier
        available_budget = current_budget - allocated_budget
                           - reserved_budget
        utilisation = used_budget / current_budget

    Allocation flow
    ---------------
        1. Portfolio requests *request_pct* of its budget.
        2. The controller checks available_budget and applies
           any regime or policy adjustments.
        3. If sufficient room exists, the request is approved
           and the allocated amount is added to allocated_budget.
        4. Allocation requests that would breach the maximum
           budget are partially fulfilled (shortfall recorded
           in remaining_pct) or rejected.
        5. Released budget returns to the available pool and
           the allocation record is closed.

    Regime multipliers
    ------------------
        Each market regime has a default multiplier that
        scales every portfolio's base budget.  Multipliers can
        be overridden via :meth:`set_regime_multiplier` to
        support fine-tuning during stress events.

    Thread safety
    -------------
    All methods are ``async`` and designed to be awaited
    sequentially within a single event loop.  No external
    locking is required for single-process usage.
    """

    def __init__(
        self,
        default_budget: float = 1.0,
        min_budget: float = 0.20,
        max_budget: float = 1.0,
    ) -> None:
        """
        Initialise the budget controller.

        Args:
            default_budget: Default base budget assigned to new
                portfolios.
            min_budget: Absolute floor for any portfolio's
                current budget (even during CRISIS).
            max_budget: Absolute ceiling for any portfolio's
                current budget.
        """
        self._default_budget = default_budget
        self._min_budget = min_budget
        self._max_budget = max_budget

        self._regime_multipliers: dict[str, float] = (
            dict(_DEFAULT_REGIME_MULTIPLIERS)
        )
        self._portfolio_states: dict[str, BudgetState] = {}
        self._allocation_history: list[BudgetAllocation] = []
        self._releases_count: int = 0

        logger.info(
            "BudgetController initialised: default=%.2f, min=%.2f, max=%.2f",
            default_budget,
            min_budget,
            max_budget,
        )

    # ── Public API ────────────────────────────────────────────

    async def get_budget(
        self, portfolio_id: str, regime: str = "NORMAL"
    ) -> BudgetState:
        """
        Retrieve the current budget state for a portfolio.

        If the portfolio is unknown a new state is created with
        the default budget and the given regime's multiplier.

        Args:
            portfolio_id: Portfolio identifier.
            regime: Market regime to apply (default NORMAL).

        Returns:
            The current :class:`BudgetState` for the portfolio.
        """
        state = self._portfolio_states.get(portfolio_id)
        if state is None:
            multiplier = self._regime_multipliers.get(regime, 1.0)
            current = self._clamp(self._default_budget * multiplier)
            state = BudgetState(
                portfolio_id=portfolio_id,
                base_budget=self._default_budget,
                regime_multiplier=multiplier,
                current_budget=current,
                available_budget=current,
            )
            self._portfolio_states[portfolio_id] = state
            logger.info(
                "Created default budget state for %s (regime=%s, budget=%.2f)",
                portfolio_id,
                regime,
                current,
            )
        return state

    async def update_budget(
        self,
        portfolio_id: str,
        new_budget: float,
        reason: str = "",
    ) -> BudgetState:
        """
        Directly update a portfolio's current budget.

        The new budget is clamped to the ``[min_budget, max_budget]``
        range and the available budget is adjusted to reflect
        the change.

        Args:
            portfolio_id: Portfolio identifier.
            new_budget: Desired new current budget.
            reason: Explanation for the update.

        Returns:
            Updated :class:`BudgetState`.
        """
        state = await self.get_budget(portfolio_id)

        clamped = self._clamp(new_budget)
        delta = clamped - state.current_budget
        state.current_budget = clamped
        state.available_budget = self._clamp(
            state.available_budget + delta
        )
        state.last_updated = datetime.now()
        state.last_change_reason = reason or "manual update"

        logger.info(
            "Budget updated for %s: %.2f → %.2f (reason: %s)",
            portfolio_id,
            state.current_budget - delta,
            clamped,
            reason or "manual update",
        )
        return state

    async def recalculate_budgets(self, portfolios: list) -> dict:
        """
        Recalculate budgets for a list of portfolios.

        Each element in *portfolios* may be either a plain
        ``(portfolio_id, regime)`` tuple or a dict with keys
        ``portfolio_id`` and ``regime``.  For every portfolio
        the base budget is recomputed as ``base * multiplier``
        and the available budget is synchronised.

        Args:
            portfolios: List of portfolio descriptors.

        Returns:
            Mapping of ``portfolio_id → BudgetState`` for all
            recalculated portfolios.
        """
        results: dict[str, BudgetState] = {}

        for item in portfolios:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                portfolio_id, regime = item[0], item[1]
            elif isinstance(item, dict):
                portfolio_id = item.get("portfolio_id", "")
                regime = item.get("regime", "NORMAL")
            else:
                continue

            multiplier = self._regime_multipliers.get(regime, 1.0)
            state = self._portfolio_states.get(portfolio_id)

            if state is None:
                current = self._clamp(self._default_budget * multiplier)
                state = BudgetState(
                    portfolio_id=portfolio_id,
                    base_budget=self._default_budget,
                    regime_multiplier=multiplier,
                    current_budget=current,
                    available_budget=current,
                    last_change_reason=f"recalculate ({regime})",
                )
                self._portfolio_states[portfolio_id] = state
            else:
                new_current = self._clamp(state.base_budget * multiplier)
                delta = new_current - state.current_budget
                state.current_budget = new_current
                state.regime_multiplier = multiplier
                state.available_budget = self._clamp(
                    state.available_budget + delta
                )
                state.last_updated = datetime.now()
                state.last_change_reason = f"recalculate ({regime})"

            results[portfolio_id] = state

        logger.info(
            "Recalculated budgets for %d portfolios", len(results)
        )
        return results

    async def allocate_budget(
        self, portfolio_id: str, request_pct: float
    ) -> BudgetAllocation:
        """
        Request a budget allocation for a portfolio.

        The requested percentage is evaluated against the
        portfolio's current available budget.  If there is
        sufficient room the request is approved; otherwise
        it is partially fulfilled and the shortfall is
        recorded as ``remaining_pct``.

        Args:
            portfolio_id: Portfolio identifier.
            request_pct: Fraction of the portfolio's
                ``current_budget`` requested (0.0–1.0).

        Returns:
            :class:`BudgetAllocation` recording the request
            and its resolution.
        """
        state = await self.get_budget(portfolio_id)

        safe_pct = max(0.0, min(request_pct, 1.0))
        requested_amount = state.current_budget * safe_pct
        available = max(0.0, state.available_budget)

        if requested_amount <= available:
            allocated_amount = requested_amount
            approved = True
        else:
            allocated_amount = available
            approved = available > 0.0

        allocated_pct = (
            allocated_amount / state.current_budget
            if state.current_budget > 0
            else 0.0
        )
        remaining_pct = max(0.0, safe_pct - allocated_pct)

        if approved:
            state.allocated_budget += allocated_amount
            state.available_budget = max(
                0.0, state.available_budget - allocated_amount
            )
            state.last_updated = datetime.now()
            state.last_change_reason = (
                f"allocate {allocated_pct:.1%}"
            )

        record = BudgetAllocation(
            portfolio_id=portfolio_id,
            requested_pct=safe_pct,
            allocated_pct=allocated_pct,
            remaining_pct=remaining_pct,
            regime_at_time=self._regime_for_portfolio(portfolio_id),
            approved=approved,
        )
        self._allocation_history.append(record)

        if len(self._allocation_history) > 2000:
            self._allocation_history = self._allocation_history[-1000:]

        if approved:
            logger.info(
                "Allocated %.1f%% to %s (available=%.2f, remaining=%.1f%%)",
                allocated_pct * 100,
                portfolio_id,
                state.available_budget,
                remaining_pct * 100,
            )
        else:
            logger.warning(
                "Allocation REJECTED for %s: requested=%.1f%%, available=%.2f",
                portfolio_id,
                safe_pct * 100,
                available,
            )
        return record

    async def release_budget(
        self, portfolio_id: str, amount_pct: float
    ) -> None:
        """
        Release previously allocated budget back to the pool.

        The release amount (as a percentage of the portfolio's
        current budget) is returned to ``available_budget`` and
        deducted from ``allocated_budget``.

        Args:
            portfolio_id: Portfolio identifier.
            amount_pct: Fraction of current budget to release
                (0.0–1.0).
        """
        state = await self.get_budget(portfolio_id)

        safe_pct = max(0.0, min(amount_pct, 1.0))
        release_amount = state.current_budget * safe_pct

        actual_release = min(release_amount, state.allocated_budget)
        if actual_release <= 0:
            logger.warning(
                "Nothing to release for %s (allocated=%.2f)",
                portfolio_id,
                state.allocated_budget,
            )
            return

        state.allocated_budget = max(0.0, state.allocated_budget - actual_release)
        state.available_budget = self._clamp(
            state.available_budget + actual_release
        )
        state.last_updated = datetime.now()
        state.last_change_reason = f"release {safe_pct:.1%}"

        self._releases_count += 1

        logger.info(
            "Released %.2f (%.1f%%) from %s (allocated now=%.2f)",
            actual_release,
            safe_pct * 100,
            portfolio_id,
            state.allocated_budget,
        )

    async def get_allocation_history(
        self, portfolio_id: str, limit: int = 50
    ) -> list:
        """
        Retrieve recent allocation records for a portfolio.

        Args:
            portfolio_id: Portfolio identifier.
            limit: Maximum number of records to return
                (most recent first).

        Returns:
            List of :class:`BudgetAllocation` records, most
            recent first, up to *limit* entries.
        """
        records = [
            r
            for r in reversed(self._allocation_history)
            if r.portfolio_id == portfolio_id
        ]
        return records[:limit]

    async def set_regime_multiplier(
        self, regime: str, multiplier: float
    ) -> None:
        """
        Override the budget multiplier for a specific regime.

        Takes effect the next time :meth:`get_budget` or
        :meth:`recalculate_budgets` is called.  Does not
        retroactively recalculate existing portfolio states.

        Args:
            regime: Regime name (e.g. ``"CRISIS"``).
            multiplier: New multiplier value (0.01–2.0).
        """
        safe_mult = max(0.01, min(multiplier, 2.0))
        self._regime_multipliers[regime] = safe_mult

        logger.info(
            "Regime multiplier set: %s = %.2f (was %.2f)",
            regime,
            safe_mult,
            self._regime_multipliers.get(regime, safe_mult),
        )

    async def get_stats(self) -> BudgetStats:
        """
        Compute aggregate budget statistics.

        Returns:
            :class:`BudgetStats` snapshot across all tracked
            portfolios.
        """
        states = list(self._portfolio_states.values())
        if not states:
            return BudgetStats()

        total_portfolios = len(states)
        avg_budget = sum(s.current_budget for s in states) / total_portfolios
        used_values = [s.used_budget for s in states]
        min_used = min(used_values) if used_values else 0.0
        max_used = max(used_values) if used_values else 0.0

        alloc_count = len(self._allocation_history)

        total_budget = sum(s.current_budget for s in states)
        total_used = sum(s.used_budget for s in states)
        utilisation = (total_used / total_budget * 100) if total_budget > 0 else 0.0

        by_regime: dict[str, float] = {}
        for s in states:
            r_key = self._regime_for_portfolio(s.portfolio_id)
            by_regime[r_key] = by_regime.get(r_key, 0.0) + s.current_budget

        logger.debug(
            "Budget stats: portfolios=%d, avg=%.2f, utilisation=%.1f%%",
            total_portfolios,
            avg_budget,
            utilisation,
        )

        return BudgetStats(
            total_portfolios=total_portfolios,
            avg_budget=avg_budget,
            min_budget_used=min_used,
            max_budget_used=max_used,
            total_allocations=alloc_count,
            total_releases=self._releases_count,
            by_regime=by_regime,
            utilization_rate_pct=utilisation,
        )

    async def reset(self) -> None:
        """
        Reset the controller to its initial state.

        Clears all portfolio states, allocation history,
        release counters, and restores default regime
        multipliers.
        """
        self._portfolio_states.clear()
        self._allocation_history.clear()
        self._releases_count = 0
        self._regime_multipliers = dict(_DEFAULT_REGIME_MULTIPLIERS)

        logger.info("BudgetController reset to initial state")

    # ── Internal helpers ─────────────────────────────────────

    def _clamp(self, value: float) -> float:
        """Clamp a value to the [min, max] budget range."""
        return max(self._min_budget, min(value, self._max_budget))

    def _regime_for_portfolio(self, portfolio_id: str) -> str:
        """Return the last-change-reason-derived regime or NORMAL."""
        state = self._portfolio_states.get(portfolio_id)
        if state is None:
            return "NORMAL"
        reason = state.last_change_reason.upper()
        for regime_name in self._regime_multipliers:
            if regime_name in reason:
                return regime_name
        return "NORMAL"