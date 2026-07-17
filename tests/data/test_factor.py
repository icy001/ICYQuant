from services.data.factor import (
    FactorCatalog,
    AlphaFactor,
    FactorEvaluator,
    FactorRanker,
    FactorCombination,
    FactorExpressionEngine,
)


def test_factor_catalog():
    catalog = FactorCatalog()

    factor = AlphaFactor(
        name="momentum",
        category="MOMENTUM",
        expression="return_20",
        version="v1",
    )

    catalog.register(factor)

    assert catalog.get("momentum") == factor


def test_factor_evaluator():
    evaluator = FactorEvaluator()

    factor_values = [0.1, 0.2, 0.3, 0.4, 0.5]
    future_returns = [0.02, 0.03, 0.04, 0.05, 0.06]

    ic = evaluator.evaluate(factor_values, future_returns)

    assert ic > 0


def test_factor_ranker():
    ranker = FactorRanker()

    factors = [
        {"name": "value", "ic": 0.03},
        {"name": "momentum", "ic": 0.08},
        {"name": "quality", "ic": 0.05},
    ]

    ranked = ranker.rank(factors)

    assert ranked[0]["name"] == "momentum"
    assert ranked[1]["name"] == "quality"
    assert ranked[2]["name"] == "value"


def test_factor_combination():
    combiner = FactorCombination()

    factors = [0.1, 0.2, 0.3]
    weights = [0.4, 0.3, 0.3]

    score = combiner.combine(factors, weights)

    assert abs(score - 0.19) < 0.0001


def test_expression_engine():
    engine = FactorExpressionEngine()

    context = {"close": 120, "close_20": 100}
    result = engine.evaluate("close / close_20 - 1", context)

    assert abs(result - 0.2) < 0.0001