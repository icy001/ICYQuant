"""
Gauge metric.
"""


class Gauge:

    def __init__(self):
        self.value = 0

    def set(
        self,
        value,
    ):
        self.value = value

    def get(self):
        return self.value