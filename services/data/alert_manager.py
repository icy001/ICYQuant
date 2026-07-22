"""
Alert manager.
"""


class AlertManager:

    def __init__(self):

        self.alerts = []

    def publish(
        self,
        message,
    ):

        self.alerts.append(
            message,
        )