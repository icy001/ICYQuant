from services.data.feature_engine import (
    TechnicalFeatureCalculator,
    FactorCalculator,
    FeatureDAG,
)


def test_momentum():
    calc = TechnicalFeatureCalculator()

    value = calc.momentum(
        [
            100,
            110,
            120,
        ],
        2,
    )

    assert abs(value - 0.2) < 0.0001


def test_momentum_insufficient_data():
    calc = TechnicalFeatureCalculator()

    value = calc.momentum(
        [100, 110],
        2,
    )

    assert value == 0


def test_volatility():
    calc = TechnicalFeatureCalculator()

    value = calc.volatility([0.01, 0.02, 0.03, 0.04, 0.05])

    assert value > 0
    assert value < 0.02


def test_volatility_empty():
    calc = TechnicalFeatureCalculator()

    value = calc.volatility([])

    assert value == 0


def test_value_factor():
    calc = FactorCalculator()

    value = calc.value_factor(
        price=100,
        earnings=10,
    )

    assert value == 10


def test_value_factor_zero_earnings():
    calc = FactorCalculator()

    value = calc.value_factor(
        price=100,
        earnings=0,
    )

    assert value == 0


def test_growth_factor():
    calc = FactorCalculator()

    value = calc.growth_factor(
        current=120,
        previous=100,
    )

    assert value == 0.2


def test_feature_dag():
    dag = FeatureDAG()

    dag.add("alpha", ["momentum", "volatility"])
    dag.add("momentum", ["price"])

    deps = dag.dependencies("alpha")

    assert "momentum" in deps
    assert "volatility" in deps