"""
Risk evaluation context — Legacy and Foundation layers.

The legacy ``RiskContext`` provides a simple evaluation context for
basic risk checks. The ``FoundationRiskContext`` extends it with
runtime state, market parameters, portfolio data, and policy inputs
for the production Risk Management Platform.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Legacy Risk Context
# ---------------------------------------------------------------------------


@dataclass
class RiskContext:
    """Legacy risk evaluation context (backwards-compatible)."""

    account_id: str
    portfolio_id: str
    order: dict
    market: dict
    positions: dict


# ---------------------------------------------------------------------------
# Foundation Risk Context
# ---------------------------------------------------------------------------


@dataclass
class FoundationRiskContext:
    """
    Foundation-level risk evaluation context with full runtime data.

    Used by the production ``RiskEngine``, ``RiskExecutor``, and
    ``RiskController`` to carry all contextual information through
    the evaluation pipeline.

    Usage::

        ctx = FoundationRiskContext(
            account_id="ACC-001",
            portfolio_id="PORTFOLIO-A",
            order={"symbol": "AAPL", "quantity": 100, "side": "BUY"},
            market={"AAPL": {"price": 150.25, "volume": 500000}},
            positions={"AAPL": {"quantity": 500, "avg_price": 148.30}},
        )
    """

    # ---- Entity Identifiers ----
    account_id: str
    portfolio_id: Optional[str] = None
    strategy_id: Optional[str] = None
    request_id: Optional[str] = None

    # ---- Order / Trade Context ----
    order: Optional[dict[str, Any]] = None
    market: Optional[dict[str, Any]] = None
    positions: Optional[dict[str, Any]] = None

    # ---- Runtime State ----
    runtime_state: Optional[dict[str, Any]] = None
    lifecycle_state: Optional[str] = None

    # ---- Evaluation Parameters ----
    evaluation_params: dict[str, Any] = field(default_factory=dict)
    policy_config: Optional[dict[str, Any]] = None
    feature_data: Optional[dict[str, Any]] = None

    # ---- Risk Profile ----
    risk_level: Optional[str] = None
    profile_scope: Optional[str] = None

    # ---- Metadata ----
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_legacy(self) -> RiskContext:
        """Convert to legacy RiskContext for backward compatibility."""
        return RiskContext(
            account_id=self.account_id,
            portfolio_id=self.portfolio_id or "",
            order=self.order or {},
            market=self.market or {},
            positions=self.positions or {},
        )