from services.data.analytics import (
    FactorHealth,
    ICAnalyzer,
    FactorDecayMonitor,
    TurnoverAnalyzer,
    FactorCorrelation,
    FactorResearchReport,
)


def test_factor_health():
    health = FactorHealth()

    score = health.score(
        ic=0.1,
        decay=0.02,
        turnover=0.03,
    )

    assert score == 0.05


def test_ic_analyzer():
    analyzer = ICAnalyzer()

    factor_values = [0.1, 0.2, 0.3, 0.4, 0.5]
    returns = [0.02, 0.03, 0.04, 0.05, 0.06]

    ic = analyzer.calculate(factor_values, returns)

    assert ic > 0


def test_ic_analyzer_empty():
    analyzer = ICAnalyzer()

    ic = analyzer.calculate([], [])

    assert ic == 0


def test_factor_decay():
    monitor = FactorDecayMonitor()

    ic_series = [0.12, 0.10, 0.08, 0.05, 0.03]

    decay = monitor.analyze(ic_series)

    assert decay == -0.09


def test_factor_decay_insufficient():
    monitor = FactorDecayMonitor()

    decay = monitor.analyze([0.1])

    assert decay == 0


def test_turnover_analyzer():
    analyzer = TurnoverAnalyzer()

    previous = ["A", "B", "C", "D"]
    current = ["A", "B", "E", "F"]

    turnover = analyzer.calculate(previous, current)

    assert turnover == 0.5


def test_turnover_empty():
    analyzer = TurnoverAnalyzer()

    turnover = analyzer.calculate([], ["A", "B"])

    assert turnover == 0


def test_factor_correlation():
    correlation = FactorCorrelation()

    factor_a = [0.1, 0.2, 0.3]
    factor_b = [0.2, 0.4, 0.6]

    corr = correlation.calculate(factor_a, factor_b)

    assert corr == 0.28


def test_factor_correlation_mismatch():
    correlation = FactorCorrelation()

    factor_a = [0.1, 0.2]
    factor_b = [0.2, 0.4, 0.6]

    corr = correlation.calculate(factor_a, factor_b)

    assert corr == 0


def test_research_report():
    report = FactorResearchReport(
        factor="momentum",
        ic=0.08,
        health_score=0.05,
    )

    assert report.factor == "momentum"
    assert report.ic == 0.08