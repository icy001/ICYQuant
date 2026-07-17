"""
Pipeline status view.
"""


class PipelineView:
    def status(
        self,
        pipeline,
    ):
        return {"pipeline": pipeline, "status": "RUNNING"}