"""
Portfolio health dashboard.
"""


class HealthDashboard:

    def summary(
        self,
        health,
        metrics,
    ):

        return {
            "health": health,
            "metrics": metrics,
        }