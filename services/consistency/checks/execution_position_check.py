"""
Execution ↔ Position consistency check.

Compares execution facts against position state for quantity correctness.
Handles long/short decomposition and cumulative fill tracking.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from ..domain.consistency_check import ExecutionFact, PositionView
from ..domain.consistency_result import CheckMatrix, ConsistencyResult, MatrixRow
from ..domain.consistency_status import ConsistencyDomainStatus


def _net_from_facts(facts: List[ExecutionFact]) -> float:
    """Compute net position quantity from a list of execution facts."""
    total = 0.0
    for f in facts:
        if f.side.upper() in ("BUY", "LONG"):
            total += f.fill_quantity
        elif f.side.upper() in ("SELL", "SHORT"):
            total -= f.fill_quantity
    return total


def _net_from_view(view: PositionView) -> float:
    """Extract net quantity from a position view."""
    if view.side.upper() in ("SHORT",):
        return -view.quantity
    return view.quantity


def check_execution_position(
    execution_facts: List[ExecutionFact],
    position_view: PositionView,
    grace_period_ms: int = 5000,
) -> ConsistencyResult:
    """
    Compare execution facts with position state.

    Returns a ConsistencyResult with a matrix row for the quantity check.
    """
    result = ConsistencyResult(
        domain="POSITION",
        grace_period_ms=grace_period_ms,
    )
    matrix = CheckMatrix()

    expected_quantity = _net_from_facts(execution_facts)
    actual_quantity = _net_from_view(position_view)
    delta = actual_quantity - expected_quantity

    # Determine failure type
    tolerance = 0.0
    is_match = abs(delta) <= tolerance

    if not is_match:
        if expected_quantity == 0 and actual_quantity != 0:
            failure_type = "POSITION_OVERSTATE"
        elif actual_quantity == 0 and expected_quantity != 0:
            failure_type = "MISSING_POSITION_EVENT"
        elif actual_quantity > expected_quantity:
            failure_type = "POSITION_OVERSTATE"
        else:
            failure_type = "POSITION_MISMATCH"

        result.failure_type = failure_type
        result.expected_value = expected_quantity
        result.actual_value = actual_quantity
        result.delta = delta
        if execution_facts:
            result.source_execution_id = execution_facts[-1].execution_id
        result.status = ConsistencyDomainStatus.INCONSISTENT
    else:
        result.status = ConsistencyDomainStatus.CONSISTENT

    matrix.add_row(
        MatrixRow(
            metric="position_quantity",
            label="Position Quantity",
            expected_value=expected_quantity,
            actual_value=actual_quantity,
            delta=delta,
            pass_=is_match,
            tolerance=tolerance,
        )
    )
    result.matrix = matrix

    # Evaluate grace period
    latest_event_time = None
    for fact in execution_facts:
        if fact.occurred_at:
            if latest_event_time is None or fact.occurred_at > latest_event_time:
                latest_event_time = fact.occurred_at

    result.with_grace_evaluation(latest_event_time, position_view.last_updated_at)

    return result


class ExecutionPositionCheck:
    """Checks execution facts against position state."""

    def __init__(self, grace_period_ms: int = 5000):
        self.grace_period_ms = grace_period_ms

    def check(
        self,
        execution_facts: List[ExecutionFact],
        position_view: PositionView,
    ) -> ConsistencyResult:
        return check_execution_position(
            execution_facts=execution_facts,
            position_view=position_view,
            grace_period_ms=self.grace_period_ms,
        )
