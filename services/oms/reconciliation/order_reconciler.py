"""OrderReconciler — reconciles OMS order state with Execution state."""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from services.oms.projection.order_projection import OrderProjection
from services.oms.domain.order_status import OrderStatus
from .reconciliation_result import ReconciliationResult
from .reconciliation_status import ReconciliationStatus
from .mismatch import Mismatch
from .mismatch_severity import MismatchSeverity


class OrderReconciler:
    """Reconciles OMS order state with Execution state.

    Compares:
      - Order status
      - Filled quantity
      - Average price
    """

    def reconcile(self, oms_projection: OrderProjection,
                  execution_state: Dict[str, Any]) -> ReconciliationResult:
        """Reconcile OMS projection with execution state.

        Args:
            oms_projection: The OMS order projection.
            execution_state: Dict with keys: status, filled_quantity,
                             average_price, remaining_quantity.

        Returns:
            ReconciliationResult with any mismatches.
        """
        start = time.time()
        result = ReconciliationResult(
            order_id=oms_projection.order_id,
            oms_status=oms_projection.status.name,
            execution_status=execution_state.get("status", "UNKNOWN"),
            oms_filled_quantity=oms_projection.filled_quantity,
            execution_filled_quantity=execution_state.get("filled_quantity", 0),
            oms_average_price=oms_projection.average_price,
            execution_average_price=execution_state.get("average_price", 0),
        )

        # Check status
        exec_status = execution_state.get("status", "UNKNOWN")
        oms_status = oms_projection.status.name

        # Map execution status to comparable OMS status
        exec_oms_equivalent = self._map_execution_to_oms(exec_status)

        if exec_oms_equivalent and oms_status != exec_oms_equivalent:
            # Critical if OMS is CANCELLED but Execution is FILLED (or vice versa)
            if (oms_status == "CANCELLED" and exec_oms_equivalent == "FILLED") or \
               (oms_status == "FILLED" and exec_oms_equivalent == "CANCELLED"):
                result.add_mismatch(Mismatch.status_mismatch(
                    result.order_id, oms_status, exec_status,
                ))
                result.status = ReconciliationStatus.STATE_MISMATCH
            elif oms_projection.filled_quantity < result.execution_filled_quantity:
                result.status = ReconciliationStatus.OMS_STALE
                result.add_mismatch(Mismatch.status_mismatch(
                    result.order_id, oms_status, exec_status,
                ))
            elif oms_projection.filled_quantity > result.execution_filled_quantity:
                result.status = ReconciliationStatus.EXECUTION_STALE
                result.add_mismatch(Mismatch.status_mismatch(
                    result.order_id, oms_status, exec_status,
                ))
        else:
            # Statuses match (or execution is unknown)
            if exec_oms_equivalent is None:
                # Execution state unknown — can't reconcile
                result.status = ReconciliationStatus.UNKNOWN
            elif not result.has_mismatches:
                result.status = ReconciliationStatus.CONSISTENT

        # Check quantity (if both are in a filled state)
        if exec_oms_equivalent in ("PARTIALLY_FILLED", "FILLED"):
            exec_qty = execution_state.get("filled_quantity", 0)
            oms_qty = oms_projection.filled_quantity
            if abs(oms_qty - exec_qty) > 0.0001:
                result.add_mismatch(Mismatch.quantity_mismatch(
                    result.order_id, oms_qty, exec_qty,
                ))
                if result.status == ReconciliationStatus.CONSISTENT:
                    result.status = ReconciliationStatus.QUANTITY_MISMATCH

        # If no mismatches and status is consistent
        if not result.has_mismatches and result.status == ReconciliationStatus.UNKNOWN:
            if exec_oms_equivalent and oms_status == exec_oms_equivalent:
                result.status = ReconciliationStatus.CONSISTENT

        result.latency = time.time() - start
        return result

    @staticmethod
    def _map_execution_to_oms(exec_status: str) -> Optional[str]:
        """Map execution status string to OMS status name."""
        _map = {
            "ACCEPTED": "WORKING",
            "SUBMITTED": "WORKING",
            "PARTIALLY_FILLED": "PARTIALLY_FILLED",
            "FILLED": "FILLED",
            "CANCELLED": "CANCELLED",
            "REJECTED": "REJECTED",
            "EXPIRED": "EXPIRED",
        }
        return _map.get(exec_status)
