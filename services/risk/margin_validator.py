"""
Margin validator.
"""


class MarginValidator:

    def validate(
        self,
        available_margin,
        required_margin,
    ):

        return available_margin >= required_margin