"""
Portfolio Constraints
=====================
Enforces portfolio-level constraints on decisions.

Supports:
- Concentration limits
- Liquidity constraints
- Turnover limits
- Minimum holding period
- Custom constraint rules
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ConstraintType(str, Enum):
    """Types of portfolio constraints."""

    CONCENTRATION = "concentration"
    LIQUIDITY = "liquidity"
    TURNOVER = "turnover"
    HOLDING_PERIOD = "holding_period"
    SECTOR_LIMIT = "sector_limit"
    INSTRUMENT_LIMIT = "instrument_limit"
    CUSTOM = "custom"


class Severity(str, Enum):
    """Severity of constraint violation."""

    BLOCK = "block"  # Hard constraint - reject decision
    WARN = "warn"    # Soft constraint - flag but allow
    INFO = "info"    # Informational only


@dataclass
class ConstraintCheckResult:
    """Result of a constraint check."""

    constraint_name: str = ""
    constraint_type: ConstraintType = ConstraintType.CUSTOM
    passed: bool = True
    severity: Severity = Severity.INFO
    reason: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint_name": self.constraint_name,
            "constraint_type": self.constraint_type.value,
            "passed": self.passed,
            "severity": self.severity.value,
            "reason": self.reason,
            "details": self.details,
            "checked_at": self.checked_at.isoformat(),
        }


class PortfolioConstraints:
    """
    Portfolio Constraints Engine.

    Enforces configurable constraints on portfolio decisions:
    - Concentration limits (per instrument, sector, strategy)
    - Liquidity minimums
    - Turnover limits
    - Minimum holding periods
    - Custom constraint functions
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._initialized = False

        # Built-in constraint configurations
        self._constraints: Dict[str, Dict[str, Any]] = {}

        # Custom constraint functions
        self._custom_constraints: Dict[str, Callable] = {}

        # Metrics
        self._metrics: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return

        # Load constraints from config
        constraints_config = self._config.get("constraints", {})

        for name, cconfig in constraints_config.items():
            self._constraints[name] = {
                "type": ConstraintType(cconfig.get("type", "custom")),
                "severity": Severity(cconfig.get("severity", "warn")),
                "params": cconfig.get("params", {}),
                "enabled": cconfig.get("enabled", True),
            }

        # Default constraints if none configured
        if not self._constraints:
            self._constraints = {
                "max_position_concentration": {
                    "type": ConstraintType.CONCENTRATION,
                    "severity": Severity.BLOCK,
                    "params": {"max_weight": 0.20},
                    "enabled": True,
                },
                "min_liquidity": {
                    "type": ConstraintType.LIQUIDITY,
                    "severity": Severity.WARN,
                    "params": {"min_daily_volume": 100000},
                    "enabled": True,
                },
                "max_turnover": {
                    "type": ConstraintType.TURNOVER,
                    "severity": Severity.WARN,
                    "params": {"max_daily_turnover_pct": 0.30},
                    "enabled": True,
                },
            }

        self._initialized = True
        logger.info("PortfolioConstraints initialized with %d constraints", len(self._constraints))

    async def shutdown(self) -> None:
        self._constraints.clear()
        self._custom_constraints.clear()
        self._initialized = False
        logger.info("PortfolioConstraints shut down")

    # ------------------------------------------------------------------
    # Constraint Management
    # ------------------------------------------------------------------

    def add_constraint(
        self,
        name: str,
        constraint_type: ConstraintType,
        severity: Severity = Severity.WARN,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a new constraint."""
        self._constraints[name] = {
            "type": constraint_type,
            "severity": severity,
            "params": params or {},
            "enabled": True,
        }
        logger.debug("Constraint added: %s (%s)", name, constraint_type.value)

    def add_custom_constraint(
        self,
        name: str,
        check_fn: Callable[[Dict[str, Any], Dict[str, Any]], ConstraintCheckResult],
        severity: Severity = Severity.WARN,
    ) -> None:
        """Register a custom constraint check function."""
        self._custom_constraints[name] = check_fn
        self._constraints[name] = {
            "type": ConstraintType.CUSTOM,
            "severity": severity,
            "params": {},
            "enabled": True,
        }
        logger.debug("Custom constraint registered: %s", name)

    def enable_constraint(self, name: str) -> bool:
        if name in self._constraints:
            self._constraints[name]["enabled"] = True
            return True
        return False

    def disable_constraint(self, name: str) -> bool:
        if name in self._constraints:
            self._constraints[name]["enabled"] = False
            return True
        return False

    # ------------------------------------------------------------------
    # Constraint Checks
    # ------------------------------------------------------------------

    def _check_concentration(
        self,
        position: Dict[str, Any],
        portfolio_state: Dict[str, Any],
        params: Dict[str, Any],
    ) -> ConstraintCheckResult:
        """Check position concentration limits."""
        max_weight = params.get("max_weight", 0.20)
        weight = position.get("position_weight", position.get("allocation_weight", 0.0))

        if weight > max_weight:
            return ConstraintCheckResult(
                constraint_name="concentration",
                constraint_type=ConstraintType.CONCENTRATION,
                passed=False,
                reason=f"Position weight {weight:.2%} exceeds max {max_weight:.2%}",
                details={"weight": weight, "max_weight": max_weight},
            )
        return ConstraintCheckResult(
            constraint_name="concentration",
            constraint_type=ConstraintType.CONCENTRATION,
            passed=True,
            reason=f"Weight {weight:.2%} within limit {max_weight:.2%}",
        )

    def _check_liquidity(
        self,
        position: Dict[str, Any],
        portfolio_state: Dict[str, Any],
        params: Dict[str, Any],
    ) -> ConstraintCheckResult:
        """Check liquidity constraints."""
        min_daily_volume = params.get("min_daily_volume", 0)
        position_value = position.get("position_value", position.get("allocated_capital", 0.0))
        daily_volume = position.get("daily_volume", position.get("metadata", {}).get("daily_volume", float("inf")))

        if daily_volume < min_daily_volume:
            return ConstraintCheckResult(
                constraint_name="liquidity",
                constraint_type=ConstraintType.LIQUIDITY,
                passed=False,
                reason=f"Daily volume {daily_volume:.0f} below minimum {min_daily_volume:.0f}",
                details={"daily_volume": daily_volume, "min_daily_volume": min_daily_volume},
            )

        # Check position size vs volume (don't exceed X% of daily volume)
        max_volume_pct = params.get("max_volume_pct", 0.10)
        if daily_volume > 0 and position_value / daily_volume > max_volume_pct:
            return ConstraintCheckResult(
                constraint_name="liquidity",
                constraint_type=ConstraintType.LIQUIDITY,
                passed=False,
                reason=f"Position {position_value:.0f} exceeds {max_volume_pct:.0%} of daily volume {daily_volume:.0f}",
                details={"position_value": position_value, "daily_volume": daily_volume},
            )

        return ConstraintCheckResult(
            constraint_name="liquidity",
            constraint_type=ConstraintType.LIQUIDITY,
            passed=True,
            reason="Liquidity check passed",
        )

    def _check_turnover(
        self,
        position: Dict[str, Any],
        portfolio_state: Dict[str, Any],
        params: Dict[str, Any],
    ) -> ConstraintCheckResult:
        """Check turnover limits."""
        max_turnover_pct = params.get("max_daily_turnover_pct", 0.30)
        current_turnover = portfolio_state.get("daily_turnover", 0.0)
        position_value = position.get("position_value", position.get("allocated_capital", 0.0))
        equity = portfolio_state.get("equity", 1.0)

        new_turnover = (current_turnover + position_value) / equity if equity > 0 else 0

        if new_turnover > max_turnover_pct:
            return ConstraintCheckResult(
                constraint_name="turnover",
                constraint_type=ConstraintType.TURNOVER,
                passed=False,
                reason=f"Turnover {new_turnover:.2%} would exceed limit {max_turnover_pct:.2%}",
                details={"current_turnover": current_turnover, "new_turnover": new_turnover},
            )

        return ConstraintCheckResult(
            constraint_name="turnover",
            constraint_type=ConstraintType.TURNOVER,
            passed=True,
            reason=f"Turnover {new_turnover:.2%} within limit",
        )

    def _check_holding_period(
        self,
        position: Dict[str, Any],
        portfolio_state: Dict[str, Any],
        params: Dict[str, Any],
    ) -> ConstraintCheckResult:
        """Check minimum holding period."""
        min_holding_hours = params.get("min_holding_hours", 0)
        if min_holding_hours <= 0:
            return ConstraintCheckResult(
                constraint_name="holding_period",
                constraint_type=ConstraintType.HOLDING_PERIOD,
                passed=True,
                reason="No minimum holding period",
            )

        holdings = portfolio_state.get("holdings", {})
        instrument = position.get("instrument", "")
        if instrument in holdings:
            entry_time = holdings[instrument].get("entry_time")
            if entry_time:
                held_hours = (datetime.now(timezone.utc) - entry_time).total_seconds() / 3600
                if held_hours < min_holding_hours:
                    return ConstraintCheckResult(
                        constraint_name="holding_period",
                        constraint_type=ConstraintType.HOLDING_PERIOD,
                        passed=False,
                        reason=f"Held {held_hours:.1f}h < minimum {min_holding_hours}h",
                        details={"held_hours": held_hours, "min_hours": min_holding_hours},
                    )

        return ConstraintCheckResult(
            constraint_name="holding_period",
            constraint_type=ConstraintType.HOLDING_PERIOD,
            passed=True,
            reason="Holding period satisfied",
        )

    async def check(
        self,
        position: Dict[str, Any],
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> ConstraintCheckResult:
        """
        Run all enabled constraints on a position.

        Returns the first BLOCK-level failure, or the last result if all pass.
        """
        if not self._initialized:
            await self.initialize()

        portfolio_state = portfolio_state or {}
        final_result = ConstraintCheckResult(
            constraint_name="all",
            constraint_type=ConstraintType.CUSTOM,
            passed=True,
            reason="All constraints passed",
        )

        for name, constraint in self._constraints.items():
            if not constraint["enabled"]:
                continue

            ctype = constraint["type"]
            params = constraint["params"]
            severity = constraint["severity"]

            # Execute the check
            if ctype == ConstraintType.CONCENTRATION:
                result = self._check_concentration(position, portfolio_state, params)
            elif ctype == ConstraintType.LIQUIDITY:
                result = self._check_liquidity(position, portfolio_state, params)
            elif ctype == ConstraintType.TURNOVER:
                result = self._check_turnover(position, portfolio_state, params)
            elif ctype == ConstraintType.HOLDING_PERIOD:
                result = self._check_holding_period(position, portfolio_state, params)
            elif ctype == ConstraintType.CUSTOM and name in self._custom_constraints:
                result = self._custom_constraints[name](position, portfolio_state)
            else:
                continue

            result.constraint_name = name
            result.severity = severity

            self._metrics[f"checked_{name}"] = self._metrics.get(f"checked_{name}", 0) + 1

            if not result.passed:
                self._metrics[f"failed_{name}"] = self._metrics.get(f"failed_{name}", 0) + 1

                if severity == Severity.BLOCK:
                    logger.info("Constraint BLOCK: %s - %s", name, result.reason)
                    return result

                if severity == Severity.WARN:
                    logger.warning("Constraint WARN: %s - %s", name, result.reason)
                    final_result = result

        return final_result

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        return dict(self._metrics)

    @property
    def is_initialized(self) -> bool:
        return self._initialized
