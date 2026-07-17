"""
Data observability dashboard.
"""


class DataDashboard:
    def render(
        self,
        metrics,
    ):
        return {"status": "healthy", "metrics": metrics}