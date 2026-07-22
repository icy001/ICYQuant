"""
Automated report pipeline.
"""


class ReportPipeline:

    def __init__(
        self,
        builder,
        visualizer,
        exporter,
    ):

        self.builder = builder

        self.visualizer = visualizer

        self.exporter = exporter

    def generate(
        self,
        project_id,
        title,
        metrics,
    ):

        visualization = self.visualizer.generate(
            metrics,
        )

        report = self.builder.create(
            project_id,
            title,
            visualization,
        )

        return self.exporter.export(
            report,
        )