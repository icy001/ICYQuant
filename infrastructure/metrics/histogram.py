"""
Histogram metric.
"""


class Histogram:

    def __init__(self):
        self.values = []

    def observe(
        self,
        value,
    ):
        self.values.append(value)

    def count(self):
        return len(self.values)