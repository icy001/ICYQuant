"""
Backtest service.
"""

from .session import BacktestSession


class BacktestService:
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