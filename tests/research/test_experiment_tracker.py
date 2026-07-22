from datetime import datetime

from services.research import (
    Experiment,
    ExperimentMetrics,
    ExperimentTracker,
)


def test_experiment_tracker():

    tracker = ExperimentTracker()

    experiment = Experiment(
        "EXP001",
        "PROJECT001",
        "Momentum Test",
        "Research",
        datetime.utcnow(),
    )

    metrics = ExperimentMetrics(
        0.15,
        0.13,
        1.82,
        -0.09,
        0.28,
    )

    tracker.log(
        experiment,
        metrics,
    )

    assert tracker.get(
        "EXP001"
    )["metrics"].sharpe == 1.82