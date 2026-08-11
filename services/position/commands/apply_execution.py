"""
ApplyExecutionCommand

Translates an execution fact (ORDER_FILLED / ORDER_PARTIAL_FILL)
into a position-domain command.

Key responsibilities:
- Validate input (quantity > 0, price > 0, required fields)
- Calculate fill delta (cumulative_fill − previous_cumulative_fill)
- Detect over-fill and negative-fill-delta
- Map to position aggregate method call
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ..exceptions.position_error import (
    InvalidExecutionError,
    OverFillError,
)


@dataclass
class ApplyExecutionCommand:
    """
    Command: apply an execution fill to a position.

    Produced by ExecutionEventConsumer after translating an OMS event.
    """

    account_id: str
    instrument_id: str

    side: str  # "BUY" or "SELL"
    fill_quantity: float
    fill_price: float

    order_id: str
    execution_id: str

    # ── total order size (for over-fill protection) ────────────
    ordered_quantity: float = 0.0

    # ── fill delta tracking ───────────────────────────────────
    # The raw cumulative_fill from the OMS event *before* delta calc.
    cumulative_fill: float = 0.0
    # The previous cumulative_fill we already applied.
    previous_cumulative_fill: float = 0.0

    # ── source lineage ────────────────────────────────────────
    source_event_id: str = ""
    source_event_type: str = ""
    correlation_id: str = ""
    causation_id: str = ""
    lineage_id: str = ""

    # ── aggregate tracking ────────────────────────────────────
    aggregate_version: int = 0

    # ── metadata ──────────────────────────────────────────────
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── computed ──────────────────────────────────────────────
    _delta: Optional[float] = field(default=None, repr=False)

    # ------------------------------------------------------------------
    #  Validation
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """Validate the command. Raises InvalidExecutionError on failure."""
        if not self.account_id:
            raise InvalidExecutionError("account_id is required")
        if not self.instrument_id:
            raise InvalidExecutionError("instrument_id is required")
        if not self.order_id:
            raise InvalidExecutionError("order_id is required")
        if not self.execution_id:
            raise InvalidExecutionError("execution_id is required")
        if self.fill_quantity <= 0:
            raise InvalidExecutionError(
                f"fill_quantity must be > 0, got {self.fill_quantity}"
            )
        if self.fill_price <= 0:
            raise InvalidExecutionError(
                f"fill_price must be > 0, got {self.fill_price}"
            )
        if self.side not in ("BUY", "SELL"):
            raise InvalidExecutionError(
                f"side must be BUY or SELL, got {self.side}"
            )

    # ------------------------------------------------------------------
    #  Fill delta
    # ------------------------------------------------------------------

    @property
    def delta(self) -> float:
        """
        The incremental fill since last time we saw this order.

        delta = cumulative_fill − previous_cumulative_fill

        This prevents double-counting fills across partial fills.
        """
        if self._delta is None:
            self._delta = self.cumulative_fill - self.previous_cumulative_fill
        return self._delta

    @property
    def is_effective(self) -> bool:
        """True if this command has a positive delta (new fill to apply)."""
        return self.delta > 0

    @property
    def has_negative_delta(self) -> bool:
        """True if cumulative_fill went backwards (possible correction)."""
        return self.delta < 0

    @property
    def is_over_fill(self) -> bool:
        """
        True if cumulative fill exceeds the ordered quantity.

        Over-fill is a CRITICAL condition requiring reconciliation.
        """
        return self.ordered_quantity > 0 and self.cumulative_fill > self.ordered_quantity

    def ensure_valid_delta(self) -> None:
        """
        Verify fill is valid against the original order quantity.

        Raises:
            InvalidExecutionError: negative delta (correction required)
            OverFillError: cumulative fill exceeds order quantity
        """
        if self.has_negative_delta:
            raise InvalidExecutionError(
                f"Negative fill delta detected: "
                f"previous={self.previous_cumulative_fill}, "
                f"current={self.cumulative_fill}, "
                f"delta={self.delta}. "
                f"Possible trade correction — requires EXECUTION_CORRECTION flow."
            )
        if self.ordered_quantity > 0 and self.cumulative_fill > self.ordered_quantity:
            raise OverFillError(
                f"Over-fill: cumulative_fill={self.cumulative_fill} "
                f"exceeds ordered_quantity={self.ordered_quantity}"
            )

    # ------------------------------------------------------------------
    #  Direction helpers
    # ------------------------------------------------------------------

    @property
    def is_buy(self) -> bool:
        return self.side == "BUY"

    @property
    def is_sell(self) -> bool:
        return self.side == "SELL"

    @property
    def position_side(self) -> str:
        """Map BUY→LONG, SELL→SHORT for position domain."""
        return "LONG" if self.is_buy else "SHORT"

    @property
    def signed_quantity(self) -> float:
        """BUY→positive, SELL→negative."""
        return self.delta if self.is_buy else -self.delta

    # ------------------------------------------------------------------
    #  Output
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "instrument_id": self.instrument_id,
            "side": self.side,
            "fill_quantity": self.fill_quantity,
            "fill_price": self.fill_price,
            "order_id": self.order_id,
            "execution_id": self.execution_id,
            "cumulative_fill": self.cumulative_fill,
            "previous_cumulative_fill": self.previous_cumulative_fill,
            "delta": self.delta,
            "source_event_id": self.source_event_id,
            "source_event_type": self.source_event_type,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "lineage_id": self.lineage_id,
            "aggregate_version": self.aggregate_version,
        }
