from typing import Dict

from services.reconciliation.models.difference import CashDifference


class CashComparator:
    def compare(
        self,
        expected_balances: Dict[str, float],
        actual_balances: Dict[str, float],
    ) -> list[CashDifference]:
        differences = []
        all_users = set(expected_balances.keys()).union(actual_balances.keys())

        for user_id in all_users:
            expected = expected_balances.get(user_id, 0.0)
            actual = actual_balances.get(user_id, 0.0)

            if abs(expected - actual) > 0.0001:
                differences.append(
                    CashDifference(
                        user_id=user_id,
                        expected_balance=expected,
                        actual_balance=actual,
                        difference=expected - actual,
                    )
                )

        return differences
