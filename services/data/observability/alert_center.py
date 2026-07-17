"""
Alert center.
"""


class AlertCenter:
    def __init__(self):
        self.alerts = []

    def push(
        self,
        alert,
    ):
        self.alerts.append(alert)