"""
Bootstrap sampler.
"""

import random


class BootstrapSampler:

    def sample(
        self,
        returns,
    ):

        return [
            random.choice(returns)
            for _ in returns
        ]