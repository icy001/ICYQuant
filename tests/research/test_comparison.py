from services.research import (
    ExperimentComparator,
    ExperimentSnapshot,
    ExperimentRanking,
    ComparisonReport,
    ComparisonService,
)


def test_compare_return():
    comparator = ExperimentComparator()

    left = ExperimentSnapshot(
        experiment_id="exp-001",
        metrics={"return": 0.18},
    )

    right = ExperimentSnapshot(
        experiment_id="exp-002",
        metrics={"return": 0.15},
    )

    result = comparator.compare(left, right, "return")

    assert result.winner == "exp-001"


def test_compare_drawdown():
    comparator = ExperimentComparator()

    left = ExperimentSnapshot(
        experiment_id="exp-001",
        metrics={"max_drawdown": -0.10},
    )

    right = ExperimentSnapshot(
        experiment_id="exp-002",
        metrics={"max_drawdown": -0.15},
    )

    result = comparator.compare(left, right, "max_drawdown")

    assert result.winner == "exp-001"


def test_experiment_ranking():
    ranking = ExperimentRanking()

    experiments = [
        ExperimentSnapshot("exp-001", {"return": 0.15}),
        ExperimentSnapshot("exp-002", {"return": 0.18}),
        ExperimentSnapshot("exp-003", {"return": 0.12}),
    ]

    ranked = ranking.rank(experiments, key=lambda x: x.metrics["return"])

    assert ranked[0].experiment_id == "exp-002"
    assert ranked[1].experiment_id == "exp-001"
    assert ranked[2].experiment_id == "exp-003"


def test_comparison_report():
    report = ComparisonReport()

    comparisons = [
        {"left": "exp-001", "right": "exp-002", "winner": "exp-001"},
    ]

    result = report.generate(comparisons)

    assert result["count"] == 1


def test_comparison_service():
    report = ComparisonReport()
    service = ComparisonService(report)

    comparisons = [
        {"left": "exp-001", "right": "exp-002", "winner": "exp-001"},
        {"left": "exp-002", "right": "exp-003", "winner": "exp-003"},
    ]

    result = service.summarize(comparisons)

    assert result["count"] == 2