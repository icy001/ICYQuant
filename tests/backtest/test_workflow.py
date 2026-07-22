from services.backtest import (
    PipelineStage,
    PipelineOrchestrator,
)


def test_pipeline():

    stage = PipelineStage(
        "prepare",
        lambda ctx: {
            **ctx,
            "prepared": True,
        },
    )


    result = PipelineOrchestrator(
        [stage]
    ).execute(
        {}
    )


    assert result["prepared"]