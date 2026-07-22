"""
Latency monitor.
"""


class DataLatencyMonitor:

    def evaluate(
        self,
        latency_ms,
    ):

        return {
            "latency_ms": latency_ms,
            "healthy": latency_ms < 100,
        }