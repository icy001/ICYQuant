"""
Optimization search space.
"""


class SearchSpace:
    def __init__(
        self,
        parameters,
    ):
        self.parameters = parameters

    def combinations(self):
        result = []
        for parameter in self.parameters:
            result.extend(parameter.values)
        return result