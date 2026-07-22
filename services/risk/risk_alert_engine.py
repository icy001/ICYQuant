"""
Risk alert engine.
"""


class RiskAlertEngine:

    def evaluate(
        self,
        value,
        threshold,
    ):

        if value >= threshold.critical:

            return "CRITICAL"

        if value >= threshold.warning:

            return "WARNING"

        return "NORMAL"