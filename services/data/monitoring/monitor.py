"""
Quality monitor.
"""


class DataMonitor:
    def collect(
        self,
        data,
    ):
        return {"rows": len(data)}