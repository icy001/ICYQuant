"""
Counter metric.
"""


class Counter:

    def __init__(self):
        self.value = 0

    def increment(
        self,
        amount=1,
    ):
        self.value += amount

    def get(self):
        return self.value