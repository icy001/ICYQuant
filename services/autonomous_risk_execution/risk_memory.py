"""
Risk Memory — persistent storage of risk decision history.

Stores complete risk decision records for:
    - Risk decisions (what risk level was set, why, for which portfolio)
    - Risk budget allocations over time
    - Constraint violations and how they were resolved
    - Risk-adjusted positions history
    - Factor exposure records
    - VaR/ES estimates history

Used by:
    - Risk Optimizer for historical pattern recognition
    - Risk Budget Engine for calibration
    - Regime Risk Controller for regime-aware memory
    - Execution Learning for risk-adjusted context
    - Audit / Compliance for decision traceability
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class RiskDecisionType(Enum):
    """Types of risk decisions."""
    BUDGET_ADJUSTMENT = "budget_adjustment"
    EXPOSURE_REDUCTION = "exposure_reduction"
    LEVERAGE_CHANGE = "leverage_change"
    HEDGE_ACTIVATION = "hedge_activation"
    POSITION_LIQUIDATION = "position_liquidation"
    REGIME_SWITCH = "regime_switch"
    VOLATILITY_SCALING = "volatility_scaling"
    CONCENTRATION_FIX = "concentration_fix"
    CORRELATION_ADJUSTMENT = "correlation_adjustment"
    LIQUIDITY_OVERRIDE = "liquidity_override"
    STRESS_RESPONSE = "stress_response"
    TAIL_RISK_MITIGATION = "tail_risk_mitigation"


class Severity(Enum):
    """Severity levels for constraint violations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class ConstraintType(Enum):
    """Types of risk constraints that can be violated."""
    GROSS_EXPOSURE = "gross_exposure"
    NET_EXPOSURE = "net_exposure"
    LEVERAGE = "leverage"
    SINGLE_POSITION = "single_position"
    SECTOR_CONCENTRATION = "sector_concentration"
    FACTOR_EXPOSURE = "factor_exposure"
    LIQUIDITY = "liquidity"
    DRAWDOWN = "drawdown"
    VOLATILITY = "volatility"
    VaR_LIMIT = "var_limit"
    ES_LIMIT = "es_limit"
    CORRELATION = "correlation"


@dataclass
class FactorExposureRecord:
    """A single factor exposure snapshot."""
    factor_name: str = ""
    exposure: float = 0.0
    net_exposure: float = 0.0
    benchmark_exposure: float = 0.0


@dataclass
class VaREstimateRecord:
    """A VaR estimate snapshot."""
    confidence_level: float = 0.95
    var_value: float = 0.0
    var_pct: float = 0.0
    method: str = "historical"


@dataclass
class ESEstimateRecord:
    """An Expected Shortfall estimate snapshot."""
    confidence_level: float = 0.95
    es_value: float = 0.0
    es_pct: float = 0.0
    method: str = "historical"


@dataclass
class RiskDecision:
    """
    A complete risk decision record.

    Captures the full context of a risk decision including:
        - Which portfolio was affected
        - What type of decision was made
        - Current risk level and budget
        - Market regime at the time
        - Specific adjustments applied
        - Rationale for audit trail
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    portfolio_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    decision_type: RiskDecisionType = RiskDecisionType.BUDGET_ADJUSTMENT
    risk_level: str = "MODERATE"
    risk_budget: float = 0.0
    rationale: str = ""
    regime: str = "NORMAL"
    adjustments: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskBudgetAllocation:
    """
    A risk budget allocation record.

    Tracks how risk capital is allocated across the portfolio over time,
    including breakdowns of used vs. remaining capital and the rationale
    for the allocation decision.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    portfolio_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    regime: str = "NORMAL"
    budget_pct: float = 0.0
    allocated_capital: float = 0.0
    used_capital: float = 0.0
    remaining_capital: float = 0.0
    rationale: str = ""


@dataclass
class RiskViolation:
    """
    A constraint violation record.

    Captures when a risk constraint was breached, the actual vs. limit
    values, the severity of the breach, and how it was resolved.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    portfolio_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    constraint_type: ConstraintType = ConstraintType.GROSS_EXPOSURE
    constraint_name: str = ""
    actual_value: float = 0.0
    limit_value: float = 0.0
    severity: Severity = Severity.MEDIUM
    resolution: str = ""
    resolved_at: Optional[datetime] = None


@dataclass
class RiskMemoryStats:
    """
    Aggregate statistics from risk memory.

    Provides a summary view of all risk activity tracked in memory,
    useful for dashboards, reports, and calibration.
    """
    total_decisions: int = 0
    total_allocations: int = 0
    total_violations: int = 0
    portfolios_tracked: int = 0
    avg_risk_budget: float = 0.0
    by_regime: dict[str, int] = field(default_factory=dict)
    by_constraint: dict[str, int] = field(default_factory=dict)


class RiskMemory:
    """
    Persistent risk memory for the Autonomous Risk & Execution Platform.

    Architecture:
        - In-memory storage with configurable per-portfolio history limits
        - Append-only log for decisions, allocations, and violations
        - Query interface filtered by portfolio, time, and type
        - Aggregate statistics for monitoring and calibration

    Storage Tiers:
        1. Risk Decisions — full history of every risk adjustment
        2. Budget Allocations — time-series of risk capital allocation
        3. Violations — constraint breach log with resolution tracking
        4. Factor Exposures — per-portfolio factor exposure history
        5. VaR/ES Estimates — risk metric time-series

    Usage:
        memory = RiskMemory(max_history_per_portfolio=1000)
        await memory.store_decision(decision)
        await memory.store_budget_allocation(allocation)
        await memory.store_violation(violation)
        history = await memory.get_portfolio_history("portfolio-123")
        stats = await memory.get_stats()
    """

    def __init__(self, max_history_per_portfolio: int = 1000) -> None:
        self._max_history_per_portfolio = max_history_per_portfolio
        self._decisions: list[RiskDecision] = []
        self._allocations: list[RiskBudgetAllocation] = []
        self._violations: list[RiskViolation] = []
        self._factor_records: dict[str, list[FactorExposureRecord]] = {}
        self._var_records: dict[str, list[VaREstimateRecord]] = {}
        self._es_records: dict[str, list[ESEstimateRecord]] = {}
        self._portfolios: set[str] = set()

    # ── Decision Storage ──────────────────────────────────────

    async def store_decision(self, decision: RiskDecision) -> str:
        """
        Store a risk decision record.

        Appends the decision to the history and trims per-portfolio
        storage if the limit is exceeded.

        Args:
            decision: The RiskDecision to store.

        Returns:
            The ID of the stored decision.
        """
        self._decisions.append(decision)
        self._portfolios.add(decision.portfolio_id)
        self._trim_portfolio_history(decision.portfolio_id)
        logger.debug(
            "Stored risk decision %s for portfolio %s: %s",
            decision.id, decision.portfolio_id, decision.decision_type.value,
        )
        return decision.id

    async def store_budget_allocation(self, allocation: RiskBudgetAllocation) -> str:
        """
        Store a risk budget allocation record.

        Args:
            allocation: The RiskBudgetAllocation to store.

        Returns:
            The ID of the stored allocation.
        """
        self._allocations.append(allocation)
        self._portfolios.add(allocation.portfolio_id)
        self._trim_portfolio_history(allocation.portfolio_id)
        logger.debug(
            "Stored budget allocation %s for portfolio %s: %.1f%%",
            allocation.id, allocation.portfolio_id, allocation.budget_pct * 100,
        )
        return allocation.id

    async def store_violation(self, violation: RiskViolation) -> str:
        """
        Store a constraint violation record.

        Args:
            violation: The RiskViolation to store.

        Returns:
            The ID of the stored violation.
        """
        self._violations.append(violation)
        self._portfolios.add(violation.portfolio_id)
        self._trim_portfolio_history(violation.portfolio_id)
        logger.warning(
            "Stored violation %s for portfolio %s: %s (%s)",
            violation.id, violation.portfolio_id,
            violation.constraint_type.value, violation.severity.value,
        )
        return violation.id

    # ── Factor Exposure Storage ───────────────────────────────

    async def store_factor_exposure(
        self, portfolio_id: str, record: FactorExposureRecord
    ) -> None:
        """
        Store a factor exposure record for a portfolio.

        Args:
            portfolio_id: The portfolio identifier.
            record: The factor exposure record.
        """
        self._portfolios.add(portfolio_id)
        if portfolio_id not in self._factor_records:
            self._factor_records[portfolio_id] = []
        self._factor_records[portfolio_id].append(record)
        self._trim_portfolio_history(portfolio_id)

    # ── VaR / ES Storage ──────────────────────────────────────

    async def store_var_estimate(
        self, portfolio_id: str, record: VaREstimateRecord
    ) -> None:
        """
        Store a VaR estimate record for a portfolio.

        Args:
            portfolio_id: The portfolio identifier.
            record: The VaR estimate record.
        """
        self._portfolios.add(portfolio_id)
        if portfolio_id not in self._var_records:
            self._var_records[portfolio_id] = []
        self._var_records[portfolio_id].append(record)
        self._trim_portfolio_history(portfolio_id)

    async def store_es_estimate(
        self, portfolio_id: str, record: ESEstimateRecord
    ) -> None:
        """
        Store an Expected Shortfall estimate record for a portfolio.

        Args:
            portfolio_id: The portfolio identifier.
            record: The ES estimate record.
        """
        self._portfolios.add(portfolio_id)
        if portfolio_id not in self._es_records:
            self._es_records[portfolio_id] = []
        self._es_records[portfolio_id].append(record)
        self._trim_portfolio_history(portfolio_id)

    # ── Query Methods ─────────────────────────────────────────

    async def get_portfolio_history(
        self, portfolio_id: str, limit: int = 100
    ) -> list[RiskDecision]:
        """
        Retrieve risk decision history for a portfolio.

        Args:
            portfolio_id: The portfolio identifier.
            limit: Maximum number of records to return (most recent first).

        Returns:
            List of RiskDecision records, most recent first.
        """
        decisions = [
            d for d in self._decisions if d.portfolio_id == portfolio_id
        ]
        return list(reversed(decisions[-limit:]))

    async def get_factor_history(
        self, portfolio_id: str
    ) -> list[FactorExposureRecord]:
        """
        Retrieve factor exposure history for a portfolio.

        Args:
            portfolio_id: The portfolio identifier.

        Returns:
            List of FactorExposureRecord snapshots.
        """
        return self._factor_records.get(portfolio_id, [])

    async def get_var_history(
        self, portfolio_id: str
    ) -> list[VaREstimateRecord]:
        """
        Retrieve VaR estimate history for a portfolio.

        Args:
            portfolio_id: The portfolio identifier.

        Returns:
            List of VaREstimateRecord snapshots.
        """
        return self._var_records.get(portfolio_id, [])

    async def get_es_history(
        self, portfolio_id: str
    ) -> list[ESEstimateRecord]:
        """
        Retrieve Expected Shortfall estimate history for a portfolio.

        Args:
            portfolio_id: The portfolio identifier.

        Returns:
            List of ESEstimateRecord snapshots.
        """
        return self._es_records.get(portfolio_id, [])

    async def get_all_allocations(
        self, portfolio_id: str, limit: int = 100
    ) -> list[RiskBudgetAllocation]:
        """
        Retrieve budget allocation history for a portfolio.

        Args:
            portfolio_id: The portfolio identifier.
            limit: Maximum number of records to return.

        Returns:
            List of RiskBudgetAllocation records.
        """
        allocations = [
            a for a in self._allocations if a.portfolio_id == portfolio_id
        ]
        return allocations[-limit:]

    async def get_all_violations(
        self, portfolio_id: str, limit: int = 100
    ) -> list[RiskViolation]:
        """
        Retrieve violation history for a portfolio.

        Args:
            portfolio_id: The portfolio identifier.
            limit: Maximum number of records to return.

        Returns:
            List of RiskViolation records.
        """
        violations = [
            v for v in self._violations if v.portfolio_id == portfolio_id
        ]
        return violations[-limit:]

    async def get_open_violations(
        self, portfolio_id: str
    ) -> list[RiskViolation]:
        """
        Retrieve unresolved violations for a portfolio.

        Args:
            portfolio_id: The portfolio identifier.

        Returns:
            List of unresolved RiskViolation records.
        """
        return [
            v for v in self._violations
            if v.portfolio_id == portfolio_id and v.resolved_at is None
        ]

    # ── Maintenance ────────────────────────────────────────────

    async def clear_portfolio(self, portfolio_id: str) -> None:
        """
        Clear all history for a specific portfolio.

        Removes all decisions, allocations, violations, factor records,
        VaR records, and ES records associated with the given portfolio.

        Args:
            portfolio_id: The portfolio identifier to clear.
        """
        self._decisions = [
            d for d in self._decisions if d.portfolio_id != portfolio_id
        ]
        self._allocations = [
            a for a in self._allocations if a.portfolio_id != portfolio_id
        ]
        self._violations = [
            v for v in self._violations if v.portfolio_id != portfolio_id
        ]
        self._factor_records.pop(portfolio_id, None)
        self._var_records.pop(portfolio_id, None)
        self._es_records.pop(portfolio_id, None)
        self._portfolios.discard(portfolio_id)
        logger.info("Cleared risk memory for portfolio %s", portfolio_id)

    async def clear_all(self) -> None:
        """
        Clear all stored history across all portfolios.

        Resets the memory to an empty state.
        """
        self._decisions.clear()
        self._allocations.clear()
        self._violations.clear()
        self._factor_records.clear()
        self._var_records.clear()
        self._es_records.clear()
        self._portfolios.clear()
        logger.info("Cleared all risk memory")

    # ── Statistics ────────────────────────────────────────────

    async def get_stats(self) -> RiskMemoryStats:
        """
        Get aggregate statistics from the risk memory.

        Computes summary statistics including total counts, average
        risk budget, breakdowns by regime and constraint type.

        Returns:
            RiskMemoryStats with aggregate metrics.
        """
        stats = RiskMemoryStats(
            total_decisions=len(self._decisions),
            total_allocations=len(self._allocations),
            total_violations=len(self._violations),
            portfolios_tracked=len(self._portfolios),
        )

        if self._allocations:
            stats.avg_risk_budget = (
                sum(a.budget_pct for a in self._allocations)
                / len(self._allocations)
            )

        by_regime: dict[str, int] = {}
        for d in self._decisions:
            r = d.regime or "UNKNOWN"
            by_regime[r] = by_regime.get(r, 0) + 1
        stats.by_regime = dict(sorted(by_regime.items(), key=lambda x: -x[1]))

        by_constraint: dict[str, int] = {}
        for v in self._violations:
            c = v.constraint_type.value or "UNKNOWN"
            by_constraint[c] = by_constraint.get(c, 0) + 1
        stats.by_constraint = dict(
            sorted(by_constraint.items(), key=lambda x: -x[1])
        )

        return stats

    # ── Internal ──────────────────────────────────────────────

    def _trim_portfolio_history(self, portfolio_id: str) -> None:
        """Trim per-portfolio history to the configured max."""
        for record_list in [self._decisions, self._allocations, self._violations]:
            portfolio_records = [
                r for r in record_list if r.portfolio_id == portfolio_id
            ]
            if len(portfolio_records) > self._max_history_per_portfolio:
                excess = len(portfolio_records) - self._max_history_per_portfolio
                record_list[:] = [
                    r for r in record_list
                    if r.portfolio_id != portfolio_id
                ]
                record_list.extend(portfolio_records[excess:])

        for store in [self._factor_records, self._var_records, self._es_records]:
            if portfolio_id in store:
                records = store[portfolio_id]
                if len(records) > self._max_history_per_portfolio:
                    store[portfolio_id] = records[-self._max_history_per_portfolio:]

    # ── Properties ────────────────────────────────────────────

    @property
    def total_decisions(self) -> int:
        """Total number of decisions stored."""
        return len(self._decisions)

    @property
    def total_allocations(self) -> int:
        """Total number of budget allocations stored."""
        return len(self._allocations)

    @property
    def total_violations(self) -> int:
        """Total number of violations stored."""
        return len(self._violations)

    @property
    def portfolios_tracked(self) -> int:
        """Number of unique portfolios tracked."""
        return len(self._portfolios)