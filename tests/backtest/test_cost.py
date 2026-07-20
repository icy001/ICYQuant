from services.backtest import (
    CommissionCalculator,
    SlippageModel,
    SpreadModel,
    TransactionCost,
    TransactionCostEngine,
    CostService,
)


def test_commission():
    calculator = CommissionCalculator()

    fee = calculator.calculate(100, 100)

    assert fee > 0


def test_slippage():
    model = SlippageModel()

    price = model.calculate(100, "BUY")

    assert price > 100


def test_slippage_sell():
    model = SlippageModel()

    price = model.calculate(100, "SELL")

    assert price < 100


def test_spread():
    model = SpreadModel()

    spread_cost = model.calculate(100)

    assert spread_cost > 0


def test_transaction_cost():
    cost = TransactionCost(
        commission=1.0,
        exchange_fee=0.5,
        slippage=0.2,
        spread=0.1,
    )

    assert cost.commission == 1.0
    assert cost.exchange_fee == 0.5


def test_cost_engine():
    commission = CommissionCalculator()
    slippage = SlippageModel()
    spread = SpreadModel()

    engine = TransactionCostEngine(commission, slippage, spread)

    class Order:
        quantity = 100
        side = "BUY"

    result = engine.calculate(Order(), 100)

    assert result["commission"] > 0
    assert result["price"] > 100
    assert result["spread"] > 0


def test_cost_service():
    commission = CommissionCalculator()
    slippage = SlippageModel()
    spread = SpreadModel()

    engine = TransactionCostEngine(commission, slippage, spread)
    service = CostService(engine)

    class Order:
        quantity = 100
        side = "SELL"

    result = service.apply(Order(), 100)

    assert result["commission"] > 0
    assert result["price"] < 100