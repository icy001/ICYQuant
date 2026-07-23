"""
Central alert manager.
"""


class AlertManager:

    def __init__(
        self,
        pipeline,
        notifier,
    ):
        self.pipeline = pipeline

        self.notifier = notifier



    def handle(
        self,
        alert,
    ):
        self.pipeline.push(
            alert
        )


        return self.notifier.send(
            alert
        )