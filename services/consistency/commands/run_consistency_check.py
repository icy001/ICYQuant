"""
RunConsistencyCheck command — triggers a single cross-domain consistency check
and produces a ConsistencyCheck entity with results and triggers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..domain.consistency_check import (
    ConsistencyCheck,
    ExecutionFact,
    LedgerView,
    PositionView,
    ReconciliationTrigger,
)
from ..domain.consistency_result import ConsistencyResult
from ..domain.consistency_status import (
    ConsistencyDomainStatus,
    ReconciliationTriggerPriority,
)
from ..checks.cross_domain_check import CrossDomainCheck


@dataclass
class RunConsistencyCheck:
    """Command to execute a cross-domain consistency check."""

    account_id: str
    instrument_id: str
    execution_facts: List[ExecutionFact]
    position_view: Optional[PositionView] = None
    ledger_view: Optional[LedgerView] = None

    check_scope: str = "instrument"
    grace_period_ms: int = 5000
    correlation_id: str = ""
    lineage_id: str = ""

    check_id: str = ""

    def __post_init__(self) -> None:
        if not self.check_id:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
            self.check_id = f"CONSISTENCY-{ts}"

    def execute(self) -> ConsistencyCheck:
        """Run the consistency check and return the result."""
        cross_domain = CrossDomainCheck(grace_period_ms=self.grace_period_ms)

        if self.position_view is None or self.ledger_view is None:
            # Partial check — run only what's available
            check = ConsistencyCheck(
                check_id=self.check_id,
                account_id=self.account_id,
                instrument_id=self.instrument_id,
                check_scope=self.check_scope,
                grace_period_ms=self.grace_period_ms,
                execution_facts=self.execution_facts,
                position_view=self.position_view,
                ledger_view=self.ledger_view,
                correlation_id=self.correlation_id,
                lineage_id=self.lineage_id,
            )
            if self.position_view is not None:
                from ..checks.execution_position_check import check_execution_position
                pos_result = check_execution_position(
                    self.execution_facts,
                    self.position_view,
                    self.grace_period_ms,
                )
                check.results = [pos_result]
                check.overall_status = pos_result.status
            elif self.ledger_view is not None:
                from ..checks.execution_ledger_check import check_execution_ledger
                ledger_result = check_execution_ledger(
                    self.execution_facts,
                    self.ledger_view,
                    self.grace_period_ms,
                )
                check.results = [ledger_result]
                check.overall_status = ledger_result.status
            else:
                check.overall_status = ConsistencyDomainStatus.DEGRADED
        else:
            check = cross_domain.check(
                execution_facts=self.execution_facts,
                position_view=self.position_view,
                ledger_view=self.ledger_view,
            )
            check.check_id = self.check_id
            check.check_scope = self.check_scope
            check.correlation_id = self.correlation_id
            check.lineage_id = self.lineage_id

        # Generate reconciliation triggers for failures
        check.triggers = self._generate_triggers(check)
        return check

    def _generate_triggers(
        self,
        check: ConsistencyCheck,
    ) -> List[ReconciliationTrigger]:
        """Generate reconciliation triggers for inconsistent results."""
        triggers: List[ReconciliationTrigger] = []
        for i, result in enumerate(check.results):
            if result.status != ConsistencyDomainStatus.CONSISTENT:
                priority = self._priority_for(result.failure_type)
                triggers.append(
                    ReconciliationTrigger(
                        trigger_id=f"TRIGGER-{check.check_id}-{i}",
                        check_id=check.check_id,
                        domain=result.domain,
                        failure_type=result.failure_type,
                        expected_value=result.expected_value,
                        actual_value=result.actual_value,
                        delta=result.delta,
                        priority=priority,
                        execution_id=result.source_execution_id,
                        auto_repairable=self._is_auto_repairable(
                            result.failure_type
                        ),
                    )
                )
        return triggers

    @staticmethod
    def _priority_for(failure_type: str) -> ReconciliationTriggerPriority:
        mapping: Dict[str, ReconciliationTriggerPriority] = {
            "ACCOUNTING_IMBALANCE": ReconciliationTriggerPriority.P0,
            "LEDGER_AMOUNT_MISMATCH": ReconciliationTriggerPriority.P1,
            "POSITION_OVERSTATE": ReconciliationTriggerPriority.P1,
            "MISSING_LEDGER_ENTRY": ReconciliationTriggerPriority.P2,
            "POSITION_MISMATCH": ReconciliationTriggerPriority.P2,
            "MISSING_POSITION_EVENT": ReconciliationTriggerPriority.P2,
            "FEE_MISMATCH": ReconciliationTriggerPriority.P2,
            "COMMISSION_MISMATCH": ReconciliationTriggerPriority.P2,
        }
        return mapping.get(failure_type, ReconciliationTriggerPriority.P3)

    @staticmethod
    def _is_auto_repairable(failure_type: str) -> bool:
        auto_types = {
            "MISSING_POSITION_EVENT",
            "POSITION_MISMATCH",
            "MISSING_LEDGER_ENTRY",
            "EVENT_LAG",
        }
        return failure_type in auto_types


def run_consistency_check(
    account_id: str,
    instrument_id: str,
    execution_facts: List[ExecutionFact],
    position_view: Optional[PositionView] = None,
    ledger_view: Optional[LedgerView] = None,
    grace_period_ms: int = 5000,
) -> ConsistencyCheck:
    """Convenience function to run a single consistency check."""
    cmd = RunConsistencyCheck(
        account_id=account_id,
        instrument_id=instrument_id,
        execution_facts=execution_facts,
        position_view=position_view,
        ledger_view=ledger_view,
        grace_period_ms=grace_period_ms,
    )
    return cmd.execute()
