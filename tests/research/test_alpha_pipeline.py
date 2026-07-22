from datetime import datetime

from services.research import (
    Alpha,
    AlphaPipeline,
    AlphaSignalGenerator,
    AlphaValidator,
)


def test_alpha_pipeline():

    alpha = Alpha(
        "A001",
        "Momentum Alpha",
        "Momentum strategy",
        "F001",
        "v1",
        datetime.utcnow(),
    )

    pipeline = AlphaPipeline(
        AlphaSignalGenerator(),
        AlphaValidator(),
    )

    signal = pipeline.execute(
        alpha,
        "AAPL",
        0.95,
        "2026-07-22T10:00:00Z",
    )

    assert signal.score == 0.95