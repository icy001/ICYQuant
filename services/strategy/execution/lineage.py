"""Execution lineage for a single trade intent.

A trade is not a point: it is a chain of objects across domain boundaries::

    Strategy -> Session -> Signal -> Intent -> Risk Decision
        -> Order Request -> Order -> Fill

:class:`ExecutionLineage` links every hop together.  The ``correlation_id``
is generated once when the intent is created and every downstream object
(order request, order, fill, PnL record) carries the same id, so a single
``correlation_id`` can answer "what did this trade do" from the strategy's
signal all the way to the broker fill.

The lineage is progressively extended as the trade advances: the risk
decision id, the order request id, the order id and finally the fill id are
linked by the owning domains as each hop completes.  A lineage that reaches
a fill without an order request (or an order without a decision) signals a
broken chain and must never be trusted.
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class ExecutionLineage:
    """Links every hop of a trade from strategy to fill."""

    strategy_id: str
    session_id: str
    signal_id: str
    intent_id: str
    correlation_id: str

    decision_id: Optional[str] = None
    order_request_id: Optional[str] = None
    order_id: Optional[str] = None
    fill_id: Optional[str] = None

    def link_decision(self, decision_id: str) -> "ExecutionLineage":
        """Attach the risk decision id produced at handoff."""
        self._require("decision_id", decision_id)
        self.decision_id = decision_id
        return self

    def link_order_request(self, order_request_id: str) -> "ExecutionLineage":
        """Attach the order request id produced by the risk engine."""
        self._require("order_request_id", order_request_id)
        self.order_request_id = order_request_id
        return self

    def link_order(self, order_id: str) -> "ExecutionLineage":
        """Attach the broker / execution order id."""
        self._require("order_id", order_id)
        self.order_id = order_id
        return self

    def link_fill(self, fill_id: str) -> "ExecutionLineage":
        """Attach the fill id produced by the execution engine."""
        self._require("fill_id", fill_id)
        self.fill_id = fill_id
        return self

    def as_dict(self) -> dict[str, Optional[str]]:
        """Audit-ready plain mapping of the full lineage."""
        return {
            "strategy_id": self.strategy_id,
            "session_id": self.session_id,
            "signal_id": self.signal_id,
            "intent_id": self.intent_id,
            "correlation_id": self.correlation_id,
            "decision_id": self.decision_id,
            "order_request_id": self.order_request_id,
            "order_id": self.order_id,
            "fill_id": self.fill_id,
        }

    @staticmethod
    def _require(attribute: str, value: Optional[str]) -> None:
        if not value:
            raise ValueError("%s must not be empty" % attribute)


_correlation_counter = itertools.count(1)


def new_correlation_id(timestamp: Optional[float] = None) -> str:
    """Generate a monotonic correlation id.

    Example: ``CORR-20260813-000001``.  The correlation id is created once
    per intent and carried by every downstream object (decision, order
    request, order, fill) so the whole trade can be reconstructed from it.
    """
    reference = time.time() if timestamp is None else timestamp
    date_part = datetime.fromtimestamp(reference).strftime("%Y%m%d")
    sequence = next(_correlation_counter)
    return f"CORR-{date_part}-{sequence:06d}"


def lineage_from_intent(
    intent: Any,
    correlation_id: Optional[str] = None,
    *,
    timestamp: Optional[float] = None,
) -> ExecutionLineage:
    """Build an :class:`ExecutionLineage` from an execution intent.

    ``correlation_id`` defaults to a freshly generated one.  ``timestamp``
    only controls id generation when the correlation id is not provided.
    """
    return ExecutionLineage(
        strategy_id=intent.strategy_id,
        session_id=intent.session_id,
        signal_id=intent.signal_id,
        intent_id=intent.intent_id,
        correlation_id=correlation_id
        or new_correlation_id(timestamp),
    )
