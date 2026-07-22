"""
Portfolio simulator.
"""

from datetime import datetime

from .portfolio_snapshot import PortfolioSnapshot


class PortfolioSimulator:

    def __init__(
        self,
        cash_ledger,
        position_ledger,
        nav_engine,
    ):

        self.cash = cash_ledger

        self.positions = position_ledger

        self.nav_engine = nav_engine


    def snapshot(
        self,
        market_value,
    ):

        result = self.nav_engine.calculate(
            self.cash.balance(),
            market_value,
        )

        return PortfolioSnapshot(
            timestamp=datetime.utcnow(),
            cash=self.cash.balance(),
            market_value=market_value,
            equity=result["equity"],
            nav=result["nav"],
        )