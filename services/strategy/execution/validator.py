"""Intent validation and construction."""

from __future__ import annotations

import time
from typing import Optional

from services.strategy.execution.context import ExecutionContext
from services.strategy.execution.intent import (
    SUPPORTED_EXECUTION_POLICIES,
    SUPPORTED_SIDES,
    SUPPORTED_URGENCIES,
    ExecutionIntent,
    ExecutionIntentState,
    StrategySignal,
    intent_fingerprint,
    new_intent_id,
)


class IntentValidationError(ValueError):
    """Raised when a signal cannot become a valid execution intent."""


class IntentValidator:
    """Turns an approved signal + context snapshot into a validated intent.

    The validator enforces the strategy domain boundary:

    * only BUY / SELL sides (OPEN / CLOSE / REDUCE / REVERSE are interpreted
      later by the position / risk layers);
    * only strategy-level execution policies (MARKET / LIMIT / TWAP / VWAP /
      PASSIVE), never broker order types;
    * only LOW / NORMAL / HIGH / CRITICAL urgency;
    * positive quantities and a consistent context snapshot.

    It also stamps the intent with its fingerprint, lineage (session_id,
    correlation_id) and TTL window (created_at / market_timestamp /
    expires_at) so stale intents can never reach the risk engine.
    """

    def __init__(self, ttl_seconds: float = 2.0) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self.ttl_seconds = ttl_seconds

    def validate(
        self,
        signal: StrategySignal,
        context: ExecutionContext,
        *,
        session_id: str = "",
        correlation_id: Optional[str] = None,
        execution_policy: str = "MARKET",
        urgency: str = "NORMAL",
        now: Optional[float] = None,
    ) -> ExecutionIntent:
        """Build a validated PENDING intent or raise ``IntentValidationError``."""
        self._check_signal(signal, context)
        self._check_policy_and_urgency(execution_policy, urgency)

        reference = now if now is not None else self._reference_time(context)
        fingerprint = intent_fingerprint(
            strategy_id=signal.strategy_id,
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            side=signal.side,
            target_quantity=signal.quantity,
            execution_policy=execution_policy,
        )

        return ExecutionIntent(
            intent_id=new_intent_id(reference),
            strategy_id=signal.strategy_id,
            signal_id=signal.signal_id,
            session_id=session_id,
            correlation_id=correlation_id,
            symbol=signal.symbol,
            side=signal.side,
            target_quantity=signal.quantity,
            execution_policy=execution_policy,
            urgency=urgency,
            state=ExecutionIntentState.PENDING.value,
            intent_fingerprint=fingerprint,
            created_at=reference,
            market_timestamp=context.market_timestamp,
            expires_at=reference + self.ttl_seconds,
            metadata=dict(signal.metadata),
        )

    def is_expired(self, intent: ExecutionIntent, now: float) -> bool:
        """Return True when ``now`` is past the intent expiry (stale intent).

        An intent without an expiry (``expires_at <= 0``) never expires.
        """
        if intent.expires_at <= 0:
            return False
        return now > intent.expires_at

    # --- internal helpers -------------------------------------------------

    def _check_signal(self, signal: StrategySignal, context: ExecutionContext) -> None:
        if not signal.signal_id:
            raise IntentValidationError("signal_id is required")
        if not signal.strategy_id:
            raise IntentValidationError("strategy_id is required")
        if context.strategy_id != signal.strategy_id:
            raise IntentValidationError(
                "context strategy %s does not match signal strategy %s"
                % (context.strategy_id, signal.strategy_id)
            )
        if not signal.symbol:
            raise IntentValidationError("symbol is required")
        if signal.side not in SUPPORTED_SIDES:
            raise IntentValidationError(
                "side must be one of %s" % sorted(SUPPORTED_SIDES)
            )
        if signal.quantity <= 0:
            raise IntentValidationError("intent quantity must be positive")
        if context.market_timestamp <= 0:
            raise IntentValidationError("context market_timestamp must be positive")
        if context.lifecycle_state != "RUNNING":
            raise IntentValidationError("context lifecycle must be RUNNING")
        if context.runtime_state != "RUNNING":
            raise IntentValidationError("context runtime must be RUNNING")
        if context.readiness_state != "READY":
            raise IntentValidationError("context readiness must be READY")

    def _check_policy_and_urgency(self, execution_policy: str, urgency: str) -> None:
        if execution_policy not in SUPPORTED_EXECUTION_POLICIES:
            raise IntentValidationError(
                "execution_policy must be one of %s"
                % sorted(SUPPORTED_EXECUTION_POLICIES)
            )
        if urgency not in SUPPORTED_URGENCIES:
            raise IntentValidationError(
                "urgency must be one of %s" % sorted(SUPPORTED_URGENCIES)
            )

    @staticmethod
    def _reference_time(context: ExecutionContext) -> float:
        if context.timestamp > 0:
            return context.timestamp
        return time.time()
