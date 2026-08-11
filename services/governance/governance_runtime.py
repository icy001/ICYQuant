"""
Governance Runtime — manages the lifecycle of the governance subsystem.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional

from .governance_engine import GovernanceEngine, GovernanceEvaluation
from .decision_context import DecisionContext
from .decision_request import DecisionRequest
from .decision_result import DecisionResult, DecisionOutcome


class GovernanceRuntimeState(Enum):
    INIT = auto()
    RUNNING = auto()
    PAUSED = auto()
    DEGRADED = auto()
    STOPPED = auto()


@dataclass
class GovernanceRuntimeConfig:
    """Runtime configuration for governance."""

    evaluation_timeout_seconds: float = 5.0
    max_queued_requests: int = 1000
    audit_enabled: bool = True
    event_store_enabled: bool = True
    auto_override_emergency: bool = False


@dataclass
class GovernanceRuntimeStats:
    """Runtime statistics."""

    total_requests: int = 0
    allowed: int = 0
    rejected: int = 0
    blocked: int = 0
    review_required: int = 0
    overrides: int = 0
    errors: int = 0
    avg_latency_ms: float = 0.0
    last_evaluation_time: float = 0.0

    def record(self, evaluation: GovernanceEvaluation, latency_ms: float) -> None:
        self.total_requests += 1
        self.avg_latency_ms = (
            (self.avg_latency_ms * (self.total_requests - 1) + latency_ms) / self.total_requests
        )
        self.last_evaluation_time = time.time()
        verdict = evaluation.verdict.name
        if verdict == "ALLOW":
            self.allowed += 1
        elif verdict == "REJECT":
            self.rejected += 1
        elif verdict == "BLOCKED":
            self.blocked += 1
        elif verdict == "REVIEW":
            self.review_required += 1
        elif verdict == "OVERRIDDEN":
            self.overrides += 1


class GovernanceRuntime:
    """
    Runtime wrapper around GovernanceEngine.
    Provides lifecycle management, statistics, and optional async hooks.
    """

    def __init__(self, engine: Optional[GovernanceEngine] = None,
                 config: Optional[GovernanceRuntimeConfig] = None):
        self._engine = engine or GovernanceEngine()
        self._config = config or GovernanceRuntimeConfig()
        self._state = GovernanceRuntimeState.INIT
        self._stats = GovernanceRuntimeStats()
        self._lock = threading.Lock()

        self._on_allow: List[Callable[[GovernanceEvaluation], None]] = []
        self._on_reject: List[Callable[[GovernanceEvaluation], None]] = []
        self._on_block: List[Callable[[GovernanceEvaluation], None]] = []
        self._on_review: List[Callable[[GovernanceEvaluation], None]] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def state(self) -> GovernanceRuntimeState:
        return self._state

    @property
    def stats(self) -> GovernanceRuntimeStats:
        return self._stats

    def start(self) -> None:
        with self._lock:
            self._state = GovernanceRuntimeState.RUNNING

    def pause(self) -> None:
        with self._lock:
            self._state = GovernanceRuntimeState.PAUSED

    def resume(self) -> None:
        with self._lock:
            if self._state == GovernanceRuntimeState.PAUSED:
                self._state = GovernanceRuntimeState.RUNNING

    def stop(self) -> None:
        with self._lock:
            self._state = GovernanceRuntimeState.STOPPED

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, request: DecisionRequest, context: DecisionContext) -> DecisionResult:
        """Evaluate a decision through governance, returning a DecisionResult."""
        if self._state not in (GovernanceRuntimeState.RUNNING, GovernanceRuntimeState.DEGRADED):
            return DecisionResult(
                request_id=request.request_id,
                outcome=DecisionOutcome.REJECTED,
                reason="Governance runtime not running",
            )

        t0 = time.perf_counter()
        try:
            evaluation = self._engine.evaluate(request, context)
        except Exception as exc:
            with self._lock:
                self._stats.errors += 1
            return DecisionResult(
                request_id=request.request_id,
                outcome=DecisionOutcome.REJECTED,
                reason=f"Governance evaluation error: {exc}",
            )

        latency_ms = (time.perf_counter() - t0) * 1000

        with self._lock:
            self._stats.record(evaluation, latency_ms)

        self._fire_callbacks(evaluation)

        outcome = self._to_outcome(evaluation)
        return DecisionResult(
            request_id=request.request_id,
            decision_id=evaluation.decision_id,
            outcome=outcome,
            reason=evaluation.reason,
            audit_record=evaluation.audit_record,
        )

    def evaluate_allow_deny(self, request: DecisionRequest, context: DecisionContext) -> bool:
        """Convenience: returns True only if ALLOW."""
        result = self.evaluate(request, context)
        return result.outcome == DecisionOutcome.ALLOWED

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_allow(self, callback: Callable[[GovernanceEvaluation], None]) -> None:
        self._on_allow.append(callback)

    def on_reject(self, callback: Callable[[GovernanceEvaluation], None]) -> None:
        self._on_reject.append(callback)

    def on_block(self, callback: Callable[[GovernanceEvaluation], None]) -> None:
        self._on_block.append(callback)

    def on_review(self, callback: Callable[[GovernanceEvaluation], None]) -> None:
        self._on_review.append(callback)

    def _fire_callbacks(self, evaluation: GovernanceEvaluation) -> None:
        verdict = evaluation.verdict.name
        callbacks: List[Callable] = []
        if verdict == "ALLOW":
            callbacks = self._on_allow
        elif verdict in ("REJECT", "CANCELLED", "EXPIRED"):
            callbacks = self._on_reject
        elif verdict == "BLOCKED":
            callbacks = self._on_block
        elif verdict == "REVIEW":
            callbacks = self._on_review
        for cb in callbacks:
            try:
                cb(evaluation)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_outcome(evaluation: GovernanceEvaluation) -> DecisionOutcome:
        verdict = evaluation.verdict
        if verdict.name == "ALLOW":
            return DecisionOutcome.ALLOWED
        elif verdict.name == "REVIEW":
            return DecisionOutcome.REVIEW_REQUIRED
        elif verdict.name == "OVERRIDDEN":
            return DecisionOutcome.ALLOWED if evaluation.allow_execution else DecisionOutcome.REJECTED
        return DecisionOutcome.REJECTED

    def get_snapshot(self) -> Dict[str, Any]:
        """Return a diagnostic snapshot."""
        return {
            "state": self._state.name,
            "stats": {
                "total": self._stats.total_requests,
                "allowed": self._stats.allowed,
                "rejected": self._stats.rejected,
                "blocked": self._stats.blocked,
                "review": self._stats.review_required,
                "overrides": self._stats.overrides,
                "errors": self._stats.errors,
                "avg_latency_ms": round(self._stats.avg_latency_ms, 2),
            },
        }
