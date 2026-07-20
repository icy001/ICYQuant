"""
Exposure checker.
"""


class ExposureChecker:
    def check(
        self,
        exposure,
        rule,
    ):
        return exposure <= rule.max_exposure