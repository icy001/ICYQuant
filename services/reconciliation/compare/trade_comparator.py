from typing import List

from services.contracts.dto import TradeDTO
from services.reconciliation.models.difference import TradeDifference


class TradeComparator:
    def compare(
        self,
        expected_trades: List[TradeDTO],
        actual_trades: List[TradeDTO],
    ) -> list[TradeDifference]:
        differences = []
        expected_map = {t.trade_id: t for t in expected_trades}
        actual_map = {t.trade_id: t for t in actual_trades}

        all_ids = set(expected_map.keys()).union(actual_map.keys())

        for trade_id in all_ids:
            expected = expected_map.get(trade_id)
            actual = actual_map.get(trade_id)

            if expected is None:
                differences.append(
                    TradeDifference(
                        trade_id=trade_id,
                        difference_type="MISSING_IN_EXPECTED",
                        expected_trade=None,
                        actual_trade=actual,
                    )
                )
            elif actual is None:
                differences.append(
                    TradeDifference(
                        trade_id=trade_id,
                        difference_type="MISSING_IN_ACTUAL",
                        expected_trade=expected,
                        actual_trade=None,
                    )
                )
            elif expected != actual:
                differences.append(
                    TradeDifference(
                        trade_id=trade_id,
                        difference_type="MISMATCH",
                        expected_trade=expected,
                        actual_trade=actual,
                    )
                )

        return differences
