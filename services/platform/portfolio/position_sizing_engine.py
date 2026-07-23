"""
Position sizing intelligence.
"""


class PositionSizingEngine:

    def calculate(
        self,
        signal,
        risk,
    ):

        return {
            "signal":
                signal,
            "risk":
                risk,
            "size":
                0.0,
        }