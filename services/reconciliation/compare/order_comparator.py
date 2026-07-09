from typing import List

from services.contracts.dto import OrderDTO
from services.reconciliation.models.difference import OrderDifference


class OrderComparator:
    def compare(
        self,
        expected_orders: List[OrderDTO],
        actual_orders: List[OrderDTO],
    ) -> list[OrderDifference]:
        differences = []
        expected_map = {o.order_id: o for o in expected_orders}
        actual_map = {o.order_id: o for o in actual_orders}

        all_ids = set(expected_map.keys()).union(actual_map.keys())

        for order_id in all_ids:
            expected = expected_map.get(order_id)
            actual = actual_map.get(order_id)

            if expected is None:
                differences.append(
                    OrderDifference(
                        order_id=order_id,
                        difference_type="MISSING_IN_EXPECTED",
                        expected_order=None,
                        actual_order=actual,
                    )
                )
            elif actual is None:
                differences.append(
                    OrderDifference(
                        order_id=order_id,
                        difference_type="MISSING_IN_ACTUAL",
                        expected_order=expected,
                        actual_order=None,
                    )
                )
            elif expected.status != actual.status:
                differences.append(
                    OrderDifference(
                        order_id=order_id,
                        difference_type="STATUS_MISMATCH",
                        expected_order=expected,
                        actual_order=actual,
                    )
                )

        return differences
