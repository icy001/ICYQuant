"""
Return calculator.
"""


class ReturnCalculator:

    def calculate(
        self,
        initial_equity,
        final_equity,
    ):

        if initial_equity == 0:

            return 0.0

        return (
            final_equity -
            initial_equity
        ) / initial_equity