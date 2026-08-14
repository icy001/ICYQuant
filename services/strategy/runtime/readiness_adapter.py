"""Runtime readiness snapshot adapter.

Every readiness check must evaluate the exact same logical time point.
``RuntimeReadinessAdapter.snapshot`` produces one consistent snapshot for a
strategy instead of letting each check read state at a different moment::

    Readiness Snapshot
            |
            v
    all checks (same logical time)

Without the snapshot, ``Check A`` could read state at T1, ``Check B`` at T2
and ``Check C`` at T3, producing an inconsistent overall judgement.
"""

from __future__ import annotations

import time
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from services.strategy.readiness.state import ReadinessContext


@runtime_checkable
class RuntimeReadinessAdapter(Protocol):
    """Produces a consistent readiness snapshot for a strategy."""

    def snapshot(self, strategy_id: str) -> Mapping[str, Any]:  # pragma: no cover
        """Return a snapshot dict for ``strategy_id``.

        Expected keys: ``strategy_id``, ``control_state``, ``runtime_state``,
        ``market_data_state``, ``configuration_state``, ``risk_state``,
        ``execution_state`` and optionally ``timestamp`` / ``evaluation_id``.
        """
        ...


def snapshot_to_context(
    snapshot: Mapping[str, Any],
    timestamp: Optional[float] = None,
    evaluation_id: Optional[str] = None,
) -> ReadinessContext:
    """Normalise a raw snapshot dict into a :class:`ReadinessContext`.

    Missing states default to ``UNKNOWN`` so the gate fails safe instead of
    guessing.  The timestamp falls back to ``snapshot["timestamp"]`` and then
    to the current wall clock.
    """
    checked_at = timestamp
    if checked_at is None:
        checked_at = snapshot.get("timestamp")
    if checked_at is None:
        checked_at = time.time()

    return ReadinessContext(
        strategy_id=str(snapshot["strategy_id"]),
        control_state=str(snapshot.get("control_state", "UNKNOWN")),
        runtime_state=str(snapshot.get("runtime_state", "UNKNOWN")),
        market_data_state=str(snapshot.get("market_data_state", "UNKNOWN")),
        configuration_state=str(snapshot.get("configuration_state", "UNKNOWN")),
        risk_state=str(snapshot.get("risk_state", "UNKNOWN")),
        execution_state=str(snapshot.get("execution_state", "UNKNOWN")),
        timestamp=float(checked_at),
        evaluation_id=evaluation_id or snapshot.get("evaluation_id"),
    )
