from services.research import (
    ReportBuilder,
    VisualizationGenerator,
    ReportExporter,
    ReportPipeline,
)


def test_report_pipeline():
    pipeline = ReportPipeline(
        ReportBuilder(),
        VisualizationGenerator(),
        ReportExporter(),
    )

    result = pipeline.generate(
        "PROJECT001",
        "Momentum Research",
        {
            "sharpe": 2.15,
        },
    )

    assert result["format"] == "json"