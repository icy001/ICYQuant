"""Strategy / runtime synchronization.

The control state (what the operator asked for) and the runtime state (what
the process is actually doing) must be reconciled continuously.  The
synchronizer classifies every (control, runtime) combination and triggers
recovery when they disagree - most dangerously when the control state is
``KILLED`` but the runtime is still ``RUNNING``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReconciliationStatus(str, Enum):
    """Outcome of reconciling control state with runtime state."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class ReconciliationResult:
    """The verdict of a single reconciliation pass."""

    strategy_id: str | None
    control_state: str
    runtime_state: str
    status: str
    consistent: bool


# Fully consistent pairs: control and runtime agree.
_HEALTHY_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {
        ("STOPPED", "STOPPED"),
        ("STOPPED", "STOPPING"),
        ("STOPPED", "FAILED"),
        ("STARTING", "INITIALIZING"),
        ("STARTING", "READY"),
        ("STARTING", "RUNNING"),
        ("RUNNING", "RUNNING"),
        ("PAUSING", "RUNNING"),
        ("RESUMING", "READY"),
        ("RESUMING", "RUNNING"),
        ("STOPPING", "STOPPING"),
        ("STOPPING", "STOPPED"),
        ("KILLED", "STOPPING"),
        ("KILLED", "STOPPED"),
        ("KILLED", "FAILED"),
        ("FAILED", "FAILED"),
        ("FAILED", "STOPPED"),
    }
)

# Acceptable-but-degraded pairs: the strategy is still logically permitted
# to run, but the runtime has a health problem (or a tolerated deviation).
_DEGRADED_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {
        ("RUNNING", "DEGRADED"),
        ("PAUSED", "RUNNING"),
        ("PAUSED", "DEGRADED"),
    }
)

# Critical pairs: the control state demands the strategy is not running but
# the runtime is still alive.  This requires an emergency runtime kill.
_CRITICAL_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {
        ("KILLED", "RUNNING"),
        ("KILLED", "READY"),
        ("KILLED", "INITIALIZING"),
        ("KILLED", "DEGRADED"),
        ("KILLED", "UNKNOWN"),
        ("STOPPED", "RUNNING"),
        ("STOPPED", "READY"),
        ("STOPPED", "INITIALIZING"),
        ("STOPPED", "DEGRADED"),
        ("STOPPED", "UNKNOWN"),
        ("FAILED", "RUNNING"),
        ("FAILED", "READY"),
        ("FAILED", "INITIALIZING"),
        ("FAILED", "DEGRADED"),
        ("FAILED", "UNKNOWN"),
    }
)


def status_for(control_state: str, runtime_state: str) -> str:
    """Classify a (control, runtime) pair; default is recovery."""
    pair = (control_state, runtime_state)
    if pair in _HEALTHY_PAIRS:
        return ReconciliationStatus.HEALTHY.value
    if pair in _DEGRADED_PAIRS:
        return ReconciliationStatus.DEGRADED.value
    if pair in _CRITICAL_PAIRS:
        return ReconciliationStatus.CRITICAL.value
    return ReconciliationStatus.RECOVERY_REQUIRED.value


def is_consistent(status: str) -> bool:
    """Return True when ``status`` does not demand an immediate action."""
    return status in {
        ReconciliationStatus.HEALTHY.value,
        ReconciliationStatus.DEGRADED.value,
    }


class StrategyRuntimeSynchronizer:
    """Decides whether control state and runtime state are consistent."""

    def reconcile(
        self,
        control_state: str,
        runtime_state: str,
        strategy_id: str | None = None,
    ) -> ReconciliationResult:
        status = status_for(control_state, runtime_state)
        return ReconciliationResult(
            strategy_id=strategy_id,
            control_state=control_state,
            runtime_state=runtime_state,
            status=status,
            consistent=is_consistent(status),
        )
