"""
Compliance monitoring engine.
"""


class ComplianceMonitor:

    def check(
        self,
        action,
    ):
        return {
            "action":
                action,
            "compliant":
                True
        }