from services.strategy_eval import *


def test_strategy():

    repo = StrategyRepository()

    service = StrategyEvaluationService(repo)

    strategy = Strategy(

        "STR001",

        "Momentum Strategy",

        "VALIDATED"

    )

    service.register(strategy)

    result = service.query(
        "STR001"
    )

    assert result.name == "Momentum Strategy"
