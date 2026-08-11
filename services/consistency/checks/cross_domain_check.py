"""
Cross-domain consistency check that runs both Position and Ledger checks
in a single pass and produces an aggregated CheckMatrix.
"""

from __future__ import annotations

from typing import List

from ..domain.consistency_check import (
    ConsistencyCheck,
    ExecutionFact,
    LedgerView,
    PositionView,
)
from ..domain.consistency_result import ConsistencyResult
from ..domain.consistency_status import ConsistencyDomainStatus
from .execution_ledger_check import ExecutionLedgerCheck
from .execution_position_check import ExecutionPositionCheck


class CrossDomainCheck:
    """Combined position + ledger consistency check."""

    def __init__(self, grace_period_ms: int = 5000):
        self.grace_period_ms = grace_period_ms
        self._position_check = ExecutionPositionCheck(grace_period_ms)
        self._ledger_check = ExecutionLedgerCheck(grace_period_ms)

    def check(
        self,
        execution_facts: List[ExecutionFact],
        position_view: PositionView,
        ledger_view: LedgerView,
    ) -> ConsistencyCheck:
        """
        Run both position and ledger checks, aggregating into a single
        ConsistencyCheck with an overall status.
        """
        check = ConsistencyCheck(
            check_id="",  # populated by caller
            account_id=position_view.account_id,
            instrument_id=position_view.instrument_id,
            check_scope="instrument",
            grace_period_ms=self.grace_period_ms,
            execution_facts=execution_facts,
            position_view=position_view,
            ledger_view=ledger_view,
        )

        pos_result = self._position_check.check(execution_facts, position_view)
        ledger_result = self._ledger_check.check(execution_facts, ledger_view)

        check.results = [pos_result, ledger_result]

        # Determine overall status — worst status wins
        if (
            pos_result.status == ConsistencyDomainStatus.CONSISTENT
            and ledger_result.status == ConsistencyDomainStatus.CONSISTENT
        ):
            check.overall_status = ConsistencyDomainStatus.CONSISTENT
        elif (
            pos_result.status == ConsistencyDomainStatus.INCONSISTENT
            or ledger_result.status == ConsistencyDomainStatus.INCONSISTENT
        ):
            check.overall_status = ConsistencyDomainStatus.INCONSISTENT
        else:
            check.overall_status = ConsistencyDomainStatus.DEGRADED

        return check
