"""Strategy execution intent model.

An execution intent is what a strategy is *prepared to send* into the trading
system.  It is deliberately NOT an order::

    Signal != Execution Intent != Order Request

A signal answers *what the strategy believes should happen* (side, symbol,
quantity); an intent adds *how urgently* and *which execution policy*; only
the execution domain turns an intent into concrete broker order(s).  Strategy
intents therefore never carry broker details (broker account, broker /
exchange order ids, FIX session, broker route, credentials).
"""

from __future__ import annotations

import hashlib
import itertools
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


#: Sides a strategy intent may express.  Complex semantics (OPEN / CLOSE /
#: REDUCE / REVERSE) are interpreted later by the position / risk layers.
SUPPORTED_SIDES: frozenset[str] = frozenset({"BUY", "SELL"})

#: Strategy-level execution policies.  These are NOT broker order types;
#: the execution engine translates them into concrete orders later.
SUPPORTED_EXECUTION_POLICIES: frozenset[str] = frozenset(
    {"MARKET", "LIMIT", "TWAP", "VWAP", "PASSIVE"}
)

#: How urgently the strategy wants the intent executed.
SUPPORTED_URGENCIES: frozenset[str] = frozenset(
    {"LOW", "NORMAL", "HIGH", "CRITICAL"}
)


class ExecutionIntentState(str, Enum):
    """Lifecycle of a single execution intent."""

    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    SUBMITTED = "SUBMITTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


#: Terminal intent states - no further transition is possible.
TERMINAL_INTENT_STATES: frozenset[str] = frozenset(
    {
        ExecutionIntentState.REJECTED,
        ExecutionIntentState.EXPIRED,
        ExecutionIntentState.CANCELLED,
    }
)


def intent_state_value(state: "str | ExecutionIntentState") -> str:
    """Normalise an intent state to its plain string form."""
    if isinstance(state, ExecutionIntentState):
        return state.value
    return state


def is_terminal(state: "str | ExecutionIntentState") -> bool:
    """Return True when ``state`` is terminal (REJECTED / EXPIRED / CANCELLED)."""
    return intent_state_value(state) in TERMINAL_INTENT_STATES


@dataclass(frozen=True)
class StrategySignal:
    """What the strategy believes should happen (the intent boundary input).

    A signal only answers *what* the strategy wants (side, symbol, quantity,
    confidence).  It carries no execution policy, no urgency and no broker or
    order-level detail - those belong to the intent / execution domain.
    """

    signal_id: str
    strategy_id: str
    symbol: str
    side: str
    quantity: float
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionIntent:
    """What the strategy is prepared to send into the execution system.

    The intent expresses only::

        what            symbol / side / target_quantity
        how urgently    urgency
        which policy    execution_policy

    It carries full lineage (strategy_id, session_id, signal_id, intent_id,
    correlation_id) plus a fingerprint for duplicate detection and a TTL
    window (created_at / market_timestamp / expires_at) so stale intents can
    never reach the risk engine.
    """

    intent_id: str
    strategy_id: str
    signal_id: str

    symbol: str
    side: str
    target_quantity: float

    execution_policy: str
    urgency: str

    metadata: dict[str, Any] = field(default_factory=dict)

    state: str = ExecutionIntentState.PENDING.value
    session_id: str = ""
    correlation_id: Optional[str] = None
    intent_fingerprint: str = ""
    created_at: float = 0.0
    market_timestamp: float = 0.0
    expires_at: float = 0.0


_intent_counter = itertools.count(1)


def new_intent_id(timestamp: Optional[float] = None) -> str:
    """Generate a monotonically increasing intent id.

    Example: ``INTENT-20260813-000001``.  A signal may produce multiple
    intents, so the signal id can never substitute the intent id.
    """
    reference = time.time() if timestamp is None else timestamp
    date_part = datetime.fromtimestamp(reference).strftime("%Y%m%d")
    sequence = next(_intent_counter)
    return f"INTENT-{date_part}-{sequence:06d}"


def intent_fingerprint(
    *,
    strategy_id: str,
    signal_id: str,
    symbol: str,
    side: str,
    target_quantity: float,
    execution_policy: str,
) -> str:
    """Deterministic fingerprint for duplicate intent detection.

    Built from strategy_id, signal_id, symbol, side, target_quantity and
    execution_policy so the same signal replayed twice (e.g. by an event bus
    retry) can never create two intents.
    """
    material = "|".join(
        (
            strategy_id,
            signal_id,
            symbol,
            side,
            repr(target_quantity),
            execution_policy,
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
