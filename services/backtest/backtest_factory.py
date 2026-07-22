"""
Backtest factory.
"""

from datetime import datetime
from uuid import uuid4

from .backtest import Backtest


class BacktestFactory:

    def create(
        self,
        strategy_id,
    ):

        return Backtest(
            backtest_id=str(
                uuid4()
            ),
            strategy_id=strategy_id,
            started_at=datetime.utcnow(),
            ended_at=None,
        )