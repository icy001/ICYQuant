"""
Collect trace spans.
"""


class SpanCollector:

    def __init__(self):
        self.spans = []

    def collect(
        self,
        span,
    ):
        self.spans.append(span)

    def all(self):
        return self.spans