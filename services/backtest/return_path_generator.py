"""
Return path generator.
"""


class ReturnPathGenerator:

    def generate(
        self,
        sampler,
        returns,
        iterations,
    ):

        for _ in range(iterations):

            yield sampler.sample(
                returns
            )