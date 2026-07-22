"""
Alpha research pipeline.
"""


class AlphaPipeline:

    def __init__(
        self,
        generator,
        validator,
    ):

        self.generator = generator

        self.validator = validator

    def execute(
        self,
        alpha,
        symbol,
        score,
        timestamp,
    ):

        signal = self.generator.generate(
            alpha,
            symbol,
            score,
            timestamp,
        )

        if not self.validator.validate(
            signal,
        ):

            raise ValueError(
                "Invalid alpha signal."
            )

        return signal