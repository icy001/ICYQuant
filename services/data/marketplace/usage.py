"""
Dataset usage analytics.
"""


class UsageTracker:
    def __init__(self):
        self.counter = {}

    def record(
        self,
        dataset,
    ):
        self.counter[dataset] = self.counter.get(dataset, 0) + 1

    def usage(
        self,
        dataset,
    ):
        return self.counter.get(dataset, 0)