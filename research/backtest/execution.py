from typing import Dict, List

from research.orders.signal import PortfolioSignal


class PortfolioExecutor:

    def rebalance(
        self,
        signals: List[PortfolioSignal],
        prices: Dict[str, float],
        portfolio
    ) -> None:
        equity = portfolio.equity(prices)

        for signal in signals:
            if signal.symbol not in prices:
                continue

            price = prices[signal.symbol]
            if price <= 0:
                continue

            target_value = equity * signal.target_weight
            target_quantity = target_value / price

            portfolio.set_target(
                signal.symbol,
                target_quantity,
                price
            )