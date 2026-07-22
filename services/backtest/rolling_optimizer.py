"""
Rolling optimization.
"""


class RollingOptimizer:

    def optimize(
        self,
        optimizer,
        parameter_space,
    ):

        return list(
            optimizer.generate(
                parameter_space
            )
        )