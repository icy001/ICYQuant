"""
Risk rule monitor.
"""


class RiskRuleMonitor:
    def check(
        self,
        risk_value,
        limit,
    ):
        return risk_value > limit