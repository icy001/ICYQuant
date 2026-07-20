from services.backtest import (
    AlphaCalculator,
    BetaCalculator,
    Benchmark,
    AttributionAnalyzer,
    BenchmarkService,
)


def test_alpha():
    calculator = AlphaCalculator()

    alpha = calculator.calculate(0.15, 0.10)

    assert abs(alpha - 0.05) < 1e-10


def test_beta():
    calculator = BetaCalculator()

    beta = calculator.calculate(0.02, 0.04)

    assert beta == 0.5


def test_beta_zero_variance():
    calculator = BetaCalculator()

    beta = calculator.calculate(0.02, 0)

    assert beta == 0


def test_benchmark():
    benchmark = Benchmark(
        name="SPX",
        returns=[0.01, 0.02, 0.03],
    )

    assert benchmark.name == "SPX"
    assert benchmark.returns == [0.01, 0.02, 0.03]


def test_attribution():
    analyzer = AttributionAnalyzer()

    result = analyzer.analyze({"sector_a": 0.05, "sector_b": 0.03})

    assert result["contributions"] == {"sector_a": 0.05, "sector_b": 0.03}


def test_benchmark_service():
    alpha = AlphaCalculator()
    beta = BetaCalculator()
    attribution = AttributionAnalyzer()

    service = BenchmarkService(alpha, beta, attribution)

    result = service.analyze(0.15, 0.10)

    assert abs(result["alpha"] - 0.05) < 1e-10