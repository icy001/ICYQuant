from services.strategy.feedback import (
    FeedbackOptimizer,
    PerformanceScore,
    AlphaDecayDetector,
    StrategyRanker,
)


def test_increase_good_strategy():
    optimizer = FeedbackOptimizer()

    score = PerformanceScore(
        strategy_id="momentum",
        sharpe=2.5,
        pnl=10000,
        drawdown=0.05,
        win_rate=0.7,
    )

    factor = optimizer.adjust_weight(score)

    assert factor == 1.2


def test_reduce_bad_strategy():
    optimizer = FeedbackOptimizer()

    score = PerformanceScore(
        strategy_id="bad_strategy",
        sharpe=0.5,
        pnl=-5000,
        drawdown=0.2,
        win_rate=0.3,
    )

    factor = optimizer.adjust_weight(score)

    assert factor == 0.8


def test_keep_normal_strategy():
    optimizer = FeedbackOptimizer()

    score = PerformanceScore(
        strategy_id="normal",
        sharpe=1.5,
        pnl=5000,
        drawdown=0.1,
        win_rate=0.55,
    )

    factor = optimizer.adjust_weight(score)

    assert factor == 1.0


def test_alpha_decay():
    detector = AlphaDecayDetector()

    decay = detector.detect(
        recent_sharpe=0.8,
        historical_sharpe=2.5,
    )

    assert decay == 1.7


def test_strategy_ranking():
    ranker = StrategyRanker()

    strategies = [
        PerformanceScore("A", 2.5, 10000, 0.05, 0.7),
        PerformanceScore("B", 1.2, 5000, 0.1, 0.55),
        PerformanceScore("C", 0.5, -2000, 0.15, 0.4),
    ]

    ranked = ranker.rank(strategies)

    assert ranked[0].strategy_id == "A"
    assert ranked[1].strategy_id == "B"
    assert ranked[2].strategy_id == "C"