"""Strategy-level execution policy.

The execution policy is the strategy's own constraint set for intents and
their handoff to risk.  It is deliberately NOT a portfolio / risk policy:
portfolio-level limits (max position, max notional, max loss) live in the
portfolio domain and are enforced by the risk engine after handoff.  This
policy only answers::

    which execution policies may an intent use?
    how large may a single intent be?
    how long may an intent live before it must be executed?
    may degraded readiness be tolerated at handoff time?

A policy with ``max_intent_quantity <= 0`` (or an empty ``allowed_policies``)
is rejected at construction so a broken policy can never silently permit
invalid intents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from services.strategy.execution.intent import SUPPORTED_EXECUTION_POLICIES


@dataclass(frozen=True)
class ExecutionPolicy:
    """Strategy-level constraints applied to intents and their risk handoff."""

    #: Execution policies this strategy may express (subset of MARKET / LIMIT
    #: / TWAP / VWAP / PASSIVE).  An intent with a policy outside this set is
    #: rejected before it ever reaches risk.
    allowed_policies: frozenset[str] = field(
        default_factory=lambda: frozenset(SUPPORTED_EXECUTION_POLICIES)
    )

    #: Maximum quantity a single intent may express.  Zero or negative means
    #: "no intent is ever allowed".
    max_intent_quantity: float = 0.0

    #: How long a validated intent may wait before it is considered stale.
    #: ``0`` disables the time limit (intents never expire).
    intent_ttl_seconds: float = 0.0

    #: Whether an intent may be handed off when readiness is only DEGRADED
    #: (soft failures) instead of READY.  Hard failures always block.
    allow_degraded_readiness: bool = False

    def __post_init__(self) -> None:
        if not self.allowed_policies:
            raise ValueError("allowed_policies must not be empty")
        unsupported = sorted(
            set(self.allowed_policies) - set(SUPPORTED_EXECUTION_POLICIES)
        )
        if unsupported:
            raise ValueError(
                "unsupported execution policies: %s" % ", ".join(unsupported)
            )
        if self.max_intent_quantity < 0:
            raise ValueError("max_intent_quantity must not be negative")
        if self.intent_ttl_seconds < 0:
            raise ValueError("intent_ttl_seconds must not be negative")

    def allows_policy(self, execution_policy: str) -> bool:
        """Return True when ``execution_policy`` is allowed by this strategy."""
        return execution_policy in self.allowed_policies

    def allows_quantity(self, target_quantity: float) -> bool:
        """Return True when ``target_quantity`` fits within the policy limit.

        A ``max_intent_quantity <= 0`` means no intent is ever allowed.
        """
        if self.max_intent_quantity <= 0:
            return False
        return 0 < target_quantity <= self.max_intent_quantity

    def ttl_seconds(self, default: Optional[float] = None) -> float:
        """Effective intent TTL: policy value, falling back to ``default``.

        Returns ``0`` when the policy disables the TTL (never expires).
        """
        if self.intent_ttl_seconds > 0:
            return self.intent_ttl_seconds
        if self.intent_ttl_seconds == 0:
            return 0.0
        return default if default is not None else 0.0
