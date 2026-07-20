from services.backtest import (
    BacktestService,
    BacktestSession,
    BacktestConfiguration,
    BacktestContext,
    BacktestStatus,
)


def test_create_session():
    service = BacktestService()

    session = service.create_session(
        session_id="bt-001",
        strategy_id="momentum",
    )

    assert session.status == "CREATED"


def test_backtest_session():
    session = BacktestSession(
        session_id="bt-002",
        strategy_id="mean_reversion",
        status="RUNNING",
    )

    assert session.session_id == "bt-002"
    assert session.strategy_id == "mean_reversion"


def test_backtest_configuration():
    config = BacktestConfiguration(
        initial_cash=100000.0,
        commission=0.001,
        slippage=0.0005,
    )

    assert config.initial_cash == 100000.0
    assert config.commission == 0.001


def test_backtest_context():
    config = BacktestConfiguration(
        initial_cash=100000.0,
        commission=0.001,
        slippage=0.0005,
    )

    context = BacktestContext(
        dataset="NASDAQ",
        configuration=config,
    )

    assert context.dataset == "NASDAQ"


def test_backtest_status_enum():
    assert BacktestStatus.CREATED == "CREATED"
    assert BacktestStatus.RUNNING == "RUNNING"
    assert BacktestStatus.COMPLETED == "COMPLETED"
    assert BacktestStatus.FAILED == "FAILED"