"""
Random search optimizer.
"""

import random


class RandomSearchOptimizer:

    def generate(
        self,
        space,
        iterations,
    ):

        keys = list(
            space.parameters.keys()
        )

        for _ in range(
            iterations
        ):

            yield {
                key: random.choice(
                    space.parameters[key]
                )
                for key in keys
            }