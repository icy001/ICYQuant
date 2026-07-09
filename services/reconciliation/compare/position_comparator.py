from typing import Dict

from services.reconciliation.models.difference import PositionDifference


class PositionComparator:
    def compare(
        self,
        expected_positions: Dict[str, float],
        actual_positions: Dict[str, float],
    ) -> list[PositionDifference]:
        differences = []
        all_symbols = set(expected_positions.keys()).union(actual_positions.keys())

        for symbol in all_symbols:
            expected = expected_positions.get(symbol, 0.0)
            actual = actual_positions.get(symbol, 0.0)

            if abs(expected - actual) > 0.0001:
                differences.append(
                    PositionDifference(
                        symbol=symbol,
                        expected_quantity=expected,
                        actual_quantity=actual,
                        difference=expected - actual,
                    )
                )

        return differences
