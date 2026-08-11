"""
Leverage Controller
===================
Unified leverage control across account, strategy, and portfolio levels.

Pipeline:
    Requested Leverage → Policy Check → Approved Leverage
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LeveragePolicyType(str, Enum):
    """Types of leverage policies."""

    FIXED = "fixed"
    DYNAMIC = "dynamic"
    VOLATILITY_SCALED = "volatility_scaled"
    DRAWDOWN_SCALED = "drawdown_scaled"


@dataclass
class LeveragePolicy:
    """A leverage control policy."""

    policy_id: str = ""
    policy_type: LeveragePolicyType = LeveragePolicyType.FIXED

    # Account-level
    max_account_leverage: float = 1.0

    # Strategy-level
    max_strategy_leverage: float = 1.0
    per_strategy_limits: Dict[str, float] = field(default_factory=dict)

    # Dynamic scaling
    volatility_target: float = 0.15
    max_leverage_at_target: float = 2.0
    min_leverage_at_target: float = 0.5

    # Drawdown protection
    max_drawdown_pct: float = 0.20
    leverage_reduction_factor: float = 0.5

    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LeverageRequest:
    """Request for leverage approval."""

    strategy_id: str = ""
    portfolio_id: str = ""
    requested_leverage: float = 1.0
    current_leverage: float = 0.0
    current_drawdown: float = 0.0
    current_volatility: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class LeverageController:
    """
    Unified Leverage Controller.

    Controls leverage at multiple levels:
    - Account-level hard caps
    - Strategy-level limits
    - Dynamic scaling based on volatility
    - Drawdown-based reduction
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._initialized = False

        # Active policies
        self._policies: Dict[str, LeveragePolicy] = {}

        # Strategy-level leverage tracking
        self._strategy_leverage: Dict[str, float] = {}

        # Metrics
        self._metrics: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return

        # Load default policy
        default_policy = LeveragePolicy(
            policy_id="default",
            policy_type=LeveragePolicyType(
                self._config.get("policy_type", "fixed")
            ),
            max_account_leverage=self._config.get("max_account_leverage", 1.0),
            max_strategy_leverage=self._config.get("max_strategy_leverage", 1.0),
            volatility_target=self._config.get("volatility_target", 0.15),
            max_drawdown_pct=self._config.get("max_drawdown_pct", 0.20),
            per_strategy_limits=self._config.get("per_strategy_limits", {}),
        )
        self._policies["default"] = default_policy

        # Load additional policies
        for pid, pconfig in self._config.get("policies", {}).items():
            self._policies[pid] = LeveragePolicy(
                policy_id=pid,
                policy_type=LeveragePolicyType(pconfig.get("type", "fixed")),
                max_account_leverage=pconfig.get("max_account_leverage", 1.0),
                max_strategy_leverage=pconfig.get("max_strategy_leverage", 1.0),
                per_strategy_limits=pconfig.get("per_strategy_limits", {}),
                enabled=pconfig.get("enabled", True),
            )

        self._initialized = True
        logger.info("LeverageController initialized with %d policies", len(self._policies))

    async def shutdown(self) -> None:
        self._policies.clear()
        self._strategy_leverage.clear()
        self._initialized = False
        logger.info("LeverageController shut down")

    # ------------------------------------------------------------------
    # Policy Management
    # ------------------------------------------------------------------

    def set_policy(self, policy: LeveragePolicy) -> None:
        self._policies[policy.policy_id] = policy
        logger.info("Leverage policy set: %s", policy.policy_id)

    def get_policy(self, policy_id: str = "default") -> Optional[LeveragePolicy]:
        return self._policies.get(policy_id)

    # ------------------------------------------------------------------
    # Leverage Approval
    # ------------------------------------------------------------------

    def _compute_dynamic_leverage(
        self,
        policy: LeveragePolicy,
        current_vol: float,
        current_drawdown: float,
    ) -> float:
        """Compute dynamically scaled leverage based on market conditions."""
        if policy.policy_type == LeveragePolicyType.FIXED:
            return policy.max_account_leverage

        base_leverage = policy.max_account_leverage

        if policy.policy_type == LeveragePolicyType.VOLATILITY_SCALED:
            if current_vol > 0 and policy.volatility_target > 0:
                scale = policy.volatility_target / current_vol
                base_leverage = policy.max_leverage_at_target * min(scale, 1.5)
                base_leverage = max(base_leverage, policy.min_leverage_at_target)

        elif policy.policy_type == LeveragePolicyType.DRAWDOWN_SCALED:
            if current_drawdown > 0:
                drawdown_ratio = current_drawdown / policy.max_drawdown_pct
                if drawdown_ratio >= 1.0:
                    base_leverage *= policy.leverage_reduction_factor * 0.5
                elif drawdown_ratio >= 0.5:
                    base_leverage *= policy.leverage_reduction_factor

        elif policy.policy_type == LeveragePolicyType.DYNAMIC:
            # Combined volatility and drawdown scaling
            if current_vol > 0 and policy.volatility_target > 0:
                vol_scale = policy.volatility_target / current_vol
                base_leverage *= min(vol_scale, 1.5)
            if current_drawdown > 0:
                dd_ratio = current_drawdown / policy.max_drawdown_pct
                if dd_ratio >= 1.0:
                    base_leverage *= 0.3
                elif dd_ratio >= 0.5:
                    base_leverage *= policy.leverage_reduction_factor

        return round(base_leverage, 4)

    async def approve(
        self,
        request: LeverageRequest,
        policy_id: str = "default",
    ) -> Dict[str, Any]:
        """
        Approve or reject a leverage request.

        Returns dict with approved_leverage, status, reason.
        """
        if not self._initialized:
            await self.initialize()

        policy = self._policies.get(policy_id)
        if not policy:
            return {
                "approved_leverage": 0.0,
                "status": "rejected",
                "reason": f"Policy {policy_id} not found",
            }

        if not policy.enabled:
            return {
                "approved_leverage": 0.0,
                "status": "rejected",
                "reason": f"Policy {policy_id} is disabled",
            }

        # Compute dynamic leverage
        approved = self._compute_dynamic_leverage(
            policy,
            request.current_volatility,
            request.current_drawdown,
        )

        # Check account-level cap
        approved = min(approved, policy.max_account_leverage)

        # Check strategy-level cap
        strategy_cap = policy.per_strategy_limits.get(
            request.strategy_id, policy.max_strategy_leverage
        )
        approved = min(approved, strategy_cap)

        # Check current strategy leverage
        current_strat_lev = self._strategy_leverage.get(request.strategy_id, 0.0)
        if current_strat_lev + request.requested_leverage > strategy_cap:
            approved = max(0.0, strategy_cap - current_strat_lev)

        # Cap at requested
        approved = min(approved, request.requested_leverage)

        status = "approved" if approved > 0 else "rejected"
        reason = (
            f"Leverage {status}: {approved:.4f} "
            f"(requested={request.requested_leverage:.2f}, "
            f"cap={strategy_cap:.2f}, policy={policy.policy_type.value})"
        )

        if approved > 0:
            self._strategy_leverage[request.strategy_id] = (
                current_strat_lev + approved
            )

        self._metrics["approved_total"] = self._metrics.get("approved_total", 0) + 1
        if status == "rejected":
            self._metrics["rejected_total"] = self._metrics.get("rejected_total", 0) + 1

        logger.debug("Leverage approval: %s", reason)

        return {
            "approved_leverage": approved,
            "status": status,
            "reason": reason,
            "policy_id": policy_id,
            "policy_type": policy.policy_type.value,
        }

    async def release_leverage(self, strategy_id: str, amount: float) -> None:
        """Release leverage back to the strategy's budget."""
        current = self._strategy_leverage.get(strategy_id, 0.0)
        self._strategy_leverage[strategy_id] = max(0.0, current - amount)

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        return {
            **self._metrics,
            "strategy_leverage": dict(self._strategy_leverage),
        }

    @property
    def is_initialized(self) -> bool:
        return self._initialized
