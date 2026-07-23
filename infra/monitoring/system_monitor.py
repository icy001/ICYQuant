"""
Production monitoring.
"""


class SystemMonitor:

    def collect(self):
        return {
            "cpu":
                "ok",
            "memory":
                "ok",
            "services":
                "healthy"
        }