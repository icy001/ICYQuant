"""
Risk budget validation.
"""


class RiskBudgetValidator:
    def validate(
        self,
        budget,
        requested,
    ):
        return budget.used_risk + requested <= budget.max_risk