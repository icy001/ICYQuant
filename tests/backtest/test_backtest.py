from services.backtest.job import BacktestJob
from services.backtest.simple_replay import ReplayEngine
from services.backtest.order_simulator import OrderSimulator
from services.backtest.backtest_repository import BacktestRepository
from services.backtest.manager import BacktestManager
from services.backtest.service import BacktestService


def test_backtest_engine():
    service = BacktestService(
        BacktestManager(
            ReplayEngine(),
            OrderSimulator(),
            BacktestRepository()
        )
    )

    job = BacktestJob(
        "BT001",
        "S001",
        "NVDA",
        "2025-01-01",
        "2025-12-31"
    )

    result = service.execute(
        job,
        [
            100,
            101,
            102
        ]
    )

    assert result["trades"] == 3