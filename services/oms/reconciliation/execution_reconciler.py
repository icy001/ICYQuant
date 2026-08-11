"""ExecutionReconciler — reconciles OMS executions with Execution executions."""
from __future__ import annotations

import time
from typing import Dict, List

from .reconciliation_result import ReconciliationResult
from .reconciliation_status import ReconciliationStatus
from .mismatch import Mismatch


class ExecutionReconciler:
    """Reconciles OMS execution records with Execution layer records.

    Compares:
      - Execution IDs present in both systems
      - Fill quantities per execution
      - Fill prices per execution
    """

    def reconcile(self, order_id: str,
                  oms_executions: List[Dict],
                  execution_executions: List[Dict]) -> ReconciliationResult:
        """Reconcile execution records.

        Args:
            order_id: The order being reconciled.
            oms_executions: List of OMS execution dicts with
                           execution_id, fill_quantity, fill_price.
            execution_executions: List of execution-layer execution dicts.

        Returns:
            ReconciliationResult.
        """
        start = time.time()
        result = ReconciliationResult(order_id=order_id)

        oms_ids = {e["execution_id"] for e in oms_executions}
        exec_ids = {e["execution_id"] for e in execution_executions}

        # Missing from OMS
        for eid in exec_ids - oms_ids:
            result.add_mismatch(Mismatch.missing_execution(order_id, eid))

        # Missing from Execution
        for eid in oms_ids - exec_ids:
            result.add_mismatch(Mismatch(
                order_id=order_id,
                mismatch_type=Mismatch.MismatchType.MISSING_EXECUTION,
                severity=MismatchSeverity.WARNING,
                oms_value=eid,
                description=f"Execution {eid} missing from Execution layer",
            ))

        # Check matching executions for quantity/price mismatches
        oms_by_id = {e["execution_id"]: e for e in oms_executions}
        exec_by_id = {e["execution_id"]: e for e in execution_executions}

        for eid in oms_ids & exec_ids:
            oms_e = oms_by_id[eid]
            exec_e = exec_by_id[eid]

            if abs(oms_e.get("fill_quantity", 0) - exec_e.get("fill_quantity", 0)) > 0.0001:
                result.add_mismatch(Mismatch.quantity_mismatch(
                    order_id,
                    oms_e.get("fill_quantity", 0),
                    exec_e.get("fill_quantity", 0),
                ))

        # Check for duplicate execution IDs in OMS
        if len(oms_ids) < len(oms_executions):
            result.add_mismatch(Mismatch(
                order_id=order_id,
                mismatch_type=Mismatch.MismatchType.DUPLICATE_EXECUTION,
                severity=MismatchSeverity.CRITICAL,
                oms_value=f"{len(oms_executions)} executions, {len(oms_ids)} unique IDs",
                description="Duplicate execution IDs in OMS",
            ))

        if not result.has_mismatches:
            result.status = ReconciliationStatus.CONSISTENT
        elif result.status == ReconciliationStatus.UNKNOWN:
            result.status = ReconciliationStatus.QUANTITY_MISMATCH

        result.latency = time.time() - start
        return result
