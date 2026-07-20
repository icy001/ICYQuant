"""
Backtest platform health check.
"""


class BacktestHealthCheck:
    def check(self):
        return {
            "status": "UP",
        }