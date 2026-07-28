"""
Backtest service.
"""

from .session import BacktestSession


class BacktestService:
    def __init__(self, manager=None):
        self.manager = manager

    def create_session(
        self,
        session_id: str,
        strategy_id: str,
    ) -> BacktestSession:
        return BacktestSession(
            session_id=session_id,
            strategy_id=strategy_id,
            status="CREATED",
        )

    def execute(self, job, data):
        return self.manager.run(job, data)