"""
Decision trace engine.
"""


class DecisionTraceEngine:

    def __init__(self):
        self.records = []

    def record(
        self,
        trace,
    ):
        self.records.append(trace)

    def history(self):
        return self.records