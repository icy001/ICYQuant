"""
Event Contract — formal definition of every event type flowing
through the cross-domain Event Bus.

Each contract declares:
- event_type:   the discriminator string (e.g. "ORDER_FILLED")
- version:      schema version for evolution
- producer:     which bounded context owns this event
- schema:       structural expectations (keys / types)
- consumers:    which domains consume this event (for routing)

Architecture principle:

    OMS        owns ORDER_* events
    Position   owns POSITION_* events
    Ledger      owns LEDGER_* events
    Execution   owns EXECUTION_* events

No domain may produce events outside its bounded context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, FrozenSet, Mapping, Optional


@dataclass(frozen=True)
class EventContract:
    """Immutable contract for a single event type."""

    event_type: str
    version: int = 1
    producer: str = ""
    description: str = ""

    # Expected keys in the payload dict.
    required_fields: FrozenSet[str] = field(default_factory=frozenset)
    optional_fields: FrozenSet[str] = field(default_factory=frozenset)

    # Consumers that are expected to handle this event.
    consumers: FrozenSet[str] = field(default_factory=frozenset)

    def validate_payload(self, payload: Mapping[str, Any]) -> None:
        """Raise ValueError if required fields are missing."""
        missing = self.required_fields - frozenset(payload.keys())
        if missing:
            raise ValueError(
                f"Event '{self.event_type}' v{self.version} "
                f"missing required fields: {missing}"
            )


# ── Canonical Event Contracts ─────────────────────────────────────────
#
# These represent the **current truth** for every event type in the system.
# When a new version is needed, register a **separate** contract for the
# new version (never mutate an existing one).

# ── Order Events (producer: OMS) ──────────────────────────────────────

EVENT_CONTRACT_ORDER_CREATED = EventContract(
    event_type="ORDER_CREATED",
    version=1,
    producer="OMS",
    description="A new order has been accepted by OMS.",
    required_fields=frozenset({"order_id", "symbol", "side", "quantity", "order_type"}),
    optional_fields=frozenset({"limit_price", "stop_price", "time_in_force", "strategy_id"}),
    consumers=frozenset({"position-service", "ledger-service", "risk-service", "audit-service"}),
)

EVENT_CONTRACT_ORDER_ROUTING_STARTED = EventContract(
    event_type="ORDER_ROUTING_STARTED",
    version=1,
    producer="OMS",
    description="OMS has started routing the order to the venue.",
    required_fields=frozenset({"order_id"}),
    optional_fields=frozenset({"venue", "routing_id"}),
    consumers=frozenset({"audit-service"}),
)

EVENT_CONTRACT_ORDER_WORKING = EventContract(
    event_type="ORDER_WORKING",
    version=1,
    producer="OMS",
    description="Order is acknowledged and working at the venue.",
    required_fields=frozenset({"order_id"}),
    optional_fields=frozenset({"venue_order_id", "working_quantity"}),
    consumers=frozenset({"position-service", "ledger-service", "risk-service", "audit-service"}),
)

EVENT_CONTRACT_ORDER_PARTIAL_FILL = EventContract(
    event_type="ORDER_PARTIAL_FILL",
    version=1,
    producer="OMS",
    description="A partial fill has been applied to the order.",
    required_fields=frozenset({"order_id", "filled_quantity", "average_price", "cumulative_quantity"}),
    optional_fields=frozenset({"execution_id", "trade_id", "venue", "fees", "commission", "liquidity_flag"}),
    consumers=frozenset({"position-service", "ledger-service", "risk-service", "audit-service"}),
)

EVENT_CONTRACT_ORDER_FILLED = EventContract(
    event_type="ORDER_FILLED",
    version=1,
    producer="OMS",
    description="The order is fully filled.",
    required_fields=frozenset({"order_id", "filled_quantity", "average_price", "cumulative_quantity"}),
    optional_fields=frozenset({"execution_id", "trade_id", "venue", "fees", "commission", "liquidity_flag", "execution_timestamp"}),
    consumers=frozenset({"position-service", "ledger-service", "risk-service", "audit-service"}),
)

EVENT_CONTRACT_ORDER_REJECTED = EventContract(
    event_type="ORDER_REJECTED",
    version=1,
    producer="OMS",
    description="The order was rejected (by venue or pre-trade risk).",
    required_fields=frozenset({"order_id", "reason"}),
    optional_fields=frozenset({"rejection_code", "venue"}),
    consumers=frozenset({"risk-service", "audit-service"}),
)

EVENT_CONTRACT_ORDER_CANCELLED = EventContract(
    event_type="ORDER_CANCELLED",
    version=1,
    producer="OMS",
    description="The order was cancelled.",
    required_fields=frozenset({"order_id", "reason"}),
    optional_fields=frozenset({"cancelled_quantity", "remaining_quantity"}),
    consumers=frozenset({"position-service", "ledger-service", "risk-service", "audit-service"}),
)

# ── Execution Events (producer: Execution) ────────────────────────────

EVENT_CONTRACT_EXECUTION_ACCEPTED = EventContract(
    event_type="EXECUTION_ACCEPTED",
    version=1,
    producer="Execution",
    description="Execution order has been accepted by the execution engine.",
    required_fields=frozenset({"execution_id", "order_id", "symbol", "side", "quantity"}),
    consumers=frozenset({"oms-service", "audit-service"}),
)

EVENT_CONTRACT_EXECUTION_REJECTED = EventContract(
    event_type="EXECUTION_REJECTED",
    version=1,
    producer="Execution",
    description="Execution order was rejected.",
    required_fields=frozenset({"execution_id", "order_id", "reason"}),
    consumers=frozenset({"oms-service", "risk-service", "audit-service"}),
)

EVENT_CONTRACT_EXECUTION_PARTIAL_FILL = EventContract(
    event_type="EXECUTION_PARTIAL_FILL",
    version=1,
    producer="Execution",
    description="Partial fill received from the venue for an execution.",
    required_fields=frozenset({"execution_id", "order_id", "filled_quantity", "price"}),
    optional_fields=frozenset({"venue", "trade_id", "liquidity_flag"}),
    consumers=frozenset({"oms-service", "position-service", "ledger-service", "audit-service"}),
)

EVENT_CONTRACT_EXECUTION_FILLED = EventContract(
    event_type="EXECUTION_FILLED",
    version=1,
    producer="Execution",
    description="Execution order is fully filled.",
    required_fields=frozenset({"execution_id", "order_id", "filled_quantity", "average_price"}),
    optional_fields=frozenset({"venue", "trade_ids", "liquidity_flag"}),
    consumers=frozenset({"oms-service", "position-service", "ledger-service", "risk-service", "audit-service"}),
)

EVENT_CONTRACT_EXECUTION_CANCELLED = EventContract(
    event_type="EXECUTION_CANCELLED",
    version=1,
    producer="Execution",
    description="Execution order was cancelled.",
    required_fields=frozenset({"execution_id", "order_id", "reason"}),
    consumers=frozenset({"oms-service", "audit-service"}),
)

# ── Position Events (producer: Position) ──────────────────────────────

EVENT_CONTRACT_POSITION_INCREASED = EventContract(
    event_type="POSITION_INCREASED",
    version=1,
    producer="Position",
    description="A position was increased via a buy fill.",
    required_fields=frozenset({"position_id", "symbol", "quantity_delta", "new_quantity", "average_price"}),
    optional_fields=frozenset({"order_id", "execution_id", "trade_id"}),
    consumers=frozenset({"risk-service", "portfolio-service", "audit-service"}),
)

EVENT_CONTRACT_POSITION_DECREASED = EventContract(
    event_type="POSITION_DECREASED",
    version=1,
    producer="Position",
    description="A position was decreased via a sell fill.",
    required_fields=frozenset({"position_id", "symbol", "quantity_delta", "new_quantity", "average_price"}),
    optional_fields=frozenset({"order_id", "execution_id", "trade_id"}),
    consumers=frozenset({"risk-service", "portfolio-service", "audit-service"}),
)

EVENT_CONTRACT_POSITION_CLOSED = EventContract(
    event_type="POSITION_CLOSED",
    version=1,
    producer="Position",
    description="A position has been fully closed.",
    required_fields=frozenset({"position_id", "symbol", "closing_quantity", "realized_pnl"}),
    optional_fields=frozenset({"order_id", "execution_id"}),
    consumers=frozenset({"risk-service", "portfolio-service", "ledger-service", "audit-service"}),
)

EVENT_CONTRACT_POSITION_REBUILT = EventContract(
    event_type="POSITION_REBUILT",
    version=1,
    producer="Position",
    description="A position has been rebuilt from the event stream.",
    required_fields=frozenset({"position_id", "symbol", "final_quantity", "average_price"}),
    consumers=frozenset({"risk-service", "portfolio-service", "audit-service"}),
)

# ── Ledger Events (producer: Ledger) ──────────────────────────────────

EVENT_CONTRACT_LEDGER_ENTRY_CREATED = EventContract(
    event_type="LEDGER_ENTRY_CREATED",
    version=1,
    producer="Ledger",
    description="A new ledger entry has been recorded.",
    required_fields=frozenset({"entry_id", "account_id", "currency", "amount", "reference_type", "reference_id"}),
    optional_fields=frozenset({"debit", "credit", "trade_value", "fees", "commission", "settlement_date"}),
    consumers=frozenset({"risk-service", "audit-service"}),
)


# ── Registry of all canonical contracts ───────────────────────────────


ALL_CONTRACTS: tuple[EventContract, ...] = (
    # Order
    EVENT_CONTRACT_ORDER_CREATED,
    EVENT_CONTRACT_ORDER_ROUTING_STARTED,
    EVENT_CONTRACT_ORDER_WORKING,
    EVENT_CONTRACT_ORDER_PARTIAL_FILL,
    EVENT_CONTRACT_ORDER_FILLED,
    EVENT_CONTRACT_ORDER_REJECTED,
    EVENT_CONTRACT_ORDER_CANCELLED,
    # Execution
    EVENT_CONTRACT_EXECUTION_ACCEPTED,
    EVENT_CONTRACT_EXECUTION_REJECTED,
    EVENT_CONTRACT_EXECUTION_PARTIAL_FILL,
    EVENT_CONTRACT_EXECUTION_FILLED,
    EVENT_CONTRACT_EXECUTION_CANCELLED,
    # Position
    EVENT_CONTRACT_POSITION_INCREASED,
    EVENT_CONTRACT_POSITION_DECREASED,
    EVENT_CONTRACT_POSITION_CLOSED,
    EVENT_CONTRACT_POSITION_REBUILT,
    # Ledger
    EVENT_CONTRACT_LEDGER_ENTRY_CREATED,
)
