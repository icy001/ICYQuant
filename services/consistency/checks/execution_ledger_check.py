"""
Execution ↔ Ledger consistency check.

Compares execution facts against ledger state for:
  - trade value
  - fee amount
  - commission amount
  - accounting balance

Each metric gets a separate matrix row so failures are pinpointed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from ..domain.consistency_check import ExecutionFact, LedgerView
from ..domain.consistency_result import CheckMatrix, ConsistencyResult, MatrixRow
from ..domain.consistency_status import ConsistencyDomainStatus


def _sum_trade_value(facts: List[ExecutionFact]) -> float:
    return sum(f.fill_quantity * f.fill_price for f in facts)


def _sum_fee(facts: List[ExecutionFact]) -> float:
    return sum(f.fee for f in facts)


def _sum_commission(facts: List[ExecutionFact]) -> float:
    return sum(f.commission for f in facts)


def check_execution_ledger(
    execution_facts: List[ExecutionFact],
    ledger_view: LedgerView,
    grace_period_ms: int = 5000,
) -> ConsistencyResult:
    """
    Compare execution facts with ledger state.

    Multi-metric check: trade value, fee, commission.
    """
    result = ConsistencyResult(
        domain="LEDGER",
        grace_period_ms=grace_period_ms,
    )
    matrix = CheckMatrix()

    expected_trade = _sum_trade_value(execution_facts)
    expected_fee = _sum_fee(execution_facts)
    expected_commission = _sum_commission(execution_facts)

    actual_trade = ledger_view.trade_amount
    actual_fee = ledger_view.fee_amount
    actual_commission = ledger_view.commission_amount

    trade_delta = actual_trade - expected_trade
    fee_delta = actual_fee - expected_fee
    commission_delta = actual_commission - expected_commission

    tolerance = 0.0
    trade_match = abs(trade_delta) <= tolerance
    fee_match = abs(fee_delta) <= tolerance
    commission_match = abs(commission_delta) <= tolerance

    all_match = trade_match and fee_match and commission_match

    # Determine failure type
    if not all_match:
        if execution_facts:
            result.source_execution_id = execution_facts[-1].execution_id
        result.status = ConsistencyDomainStatus.INCONSISTENT

        # Pick the "primary" failure type
        if not trade_match and actual_trade == 0 and expected_trade != 0:
            result.failure_type = "MISSING_LEDGER_ENTRY"
        elif not trade_match:
            result.failure_type = "LEDGER_AMOUNT_MISMATCH"
            result.expected_value = expected_trade
            result.actual_value = actual_trade
            result.delta = trade_delta
        elif not fee_match:
            result.failure_type = "FEE_MISMATCH"
            result.expected_value = expected_fee
            result.actual_value = actual_fee
            result.delta = fee_delta
        elif not commission_match:
            result.failure_type = "COMMISSION_MISMATCH"
            result.expected_value = expected_commission
            result.actual_value = actual_commission
            result.delta = commission_delta
    else:
        result.status = ConsistencyDomainStatus.CONSISTENT

    matrix.add_row(
        MatrixRow(
            metric="trade_value",
            label="Trade Value",
            expected_value=expected_trade,
            actual_value=actual_trade,
            delta=trade_delta,
            pass_=trade_match,
            tolerance=tolerance,
        )
    )
    matrix.add_row(
        MatrixRow(
            metric="fee",
            label="Fee",
            expected_value=expected_fee,
            actual_value=actual_fee,
            delta=fee_delta,
            pass_=fee_match,
            tolerance=tolerance,
        )
    )
    matrix.add_row(
        MatrixRow(
            metric="commission",
            label="Commission",
            expected_value=expected_commission,
            actual_value=actual_commission,
            delta=commission_delta,
            pass_=commission_match,
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

    result.with_grace_evaluation(latest_event_time, ledger_view.last_updated_at)

    return result


class ExecutionLedgerCheck:
    """Checks execution facts against ledger state."""

    def __init__(self, grace_period_ms: int = 5000):
        self.grace_period_ms = grace_period_ms

    def check(
        self,
        execution_facts: List[ExecutionFact],
        ledger_view: LedgerView,
    ) -> ConsistencyResult:
        return check_execution_ledger(
            execution_facts=execution_facts,
            ledger_view=ledger_view,
            grace_period_ms=self.grace_period_ms,
        )
