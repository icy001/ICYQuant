"""
Alert processing pipeline.
"""


class AlertPipeline:

    def __init__(self):
        self.alerts = []



    def push(
        self,
        alert,
    ):
        self.alerts.append(alert)