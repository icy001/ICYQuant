from services.backtest import (
    EquityCalculator,
    Portfolio,
    Position,
    CashManager,
    PortfolioService,
    CashLedger,
    PositionLedger,
    NavEngine,
)
from services.backtest.simulator import PortfolioSimulator as LegacyPortfolioSimulator
from services.backtest.portfolio_simulator import PortfolioSimulator


def test_equity_update():
    simulator = LegacyPortfolioSimulator(EquityCalculator())

    portfolio = Portfolio(
        cash=100000,
        equity=100000,
    )

    simulator.update(portfolio, market_value=25000)

    assert portfolio.equity == 125000


def test_portfolio_model():
    portfolio = Portfolio(
        cash=100000,
        equity=100000,
        positions={},
    )

    assert portfolio.cash == 100000
    assert portfolio.equity == 100000
    assert portfolio.positions == {}


def test_position_model():
    position = Position(
        symbol="AAPL",
        quantity=100,
        average_price=150.0,
    )

    assert position.symbol == "AAPL"
    assert position.quantity == 100
    assert position.average_price == 150.0


def test_cash_manager_debit():
    cash_manager = CashManager()

    result = cash_manager.debit(cash=100000, amount=15000)

    assert result == 85000


def test_cash_manager_credit():
    cash_manager = CashManager()

    result = cash_manager.credit(cash=85000, amount=15000)

    assert result == 100000


def test_equity_calculator():
    calculator = EquityCalculator()

    equity = calculator.calculate(cash=100000, market_value=25000)

    assert equity == 125000


def test_portfolio_service():
    calculator = EquityCalculator()
    simulator = LegacyPortfolioSimulator(calculator)
    service = PortfolioService(simulator)

    portfolio = Portfolio(
        cash=50000,
        equity=50000,
    )

    result = service.refresh(portfolio, market_value=10000)

    assert result.equity == 60000


def test_portfolio_snapshot():
    simulator = PortfolioSimulator(
        CashLedger(
            100000,
        ),
        PositionLedger(),
        NavEngine(),
    )

    snapshot = simulator.snapshot(
        25000,
    )

    assert snapshot.equity == 125000
    assert snapshot.nav == 125000