"""
Risk budget engine.
"""


class RiskBudgetEngine:
    def __init__(
        self,
        validator,
        calculator,
    ):
        self.validator = validator
        self.calculator = calculator

    def allocate(
        self,
        budget,
        risk_amount,
    ):
        if not self.validator.validate(budget, risk_amount):
            raise ValueError("risk budget exceeded")

        budget.used_risk += risk_amount

        return {
            "strategy_id": budget.strategy_id,
            "remaining": self.calculator.calculate_remaining(budget),
        }