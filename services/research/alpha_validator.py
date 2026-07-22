"""
Alpha validator.
"""


class AlphaValidator:

    def validate(
        self,
        signal,
    ):

        return (
            signal.score
            is not None
        )