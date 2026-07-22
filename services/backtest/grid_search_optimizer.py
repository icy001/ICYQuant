"""
Grid search optimizer.
"""

from itertools import product


class GridSearchOptimizer:

    def generate(
        self,
        space,
    ):

        keys = list(
            space.parameters.keys()
        )

        values = [
            space.parameters[k]
            for k in keys
        ]

        for combination in product(
            *values
        ):

            yield dict(
                zip(
                    keys,
                    combination,
                )
            )