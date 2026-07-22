"""
Real-time volatility monitor.
"""


class RealTimeVolatilityMonitor:

    def update(
        self,
        previous,
        current,
    ):

        return abs(
            current - previous
        )