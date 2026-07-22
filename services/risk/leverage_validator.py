"""
Leverage validator.
"""


class LeverageValidator:

    def validate(
        self,
        current_leverage,
        rule,
    ):

        return (
            current_leverage
            <=
            rule.max_leverage
        )