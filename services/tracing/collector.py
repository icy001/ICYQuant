class SpanCollector:

    def __init__(self):
        self.spans = []

    def collect(
        self,
        span
    ):
        self.spans.append(span)

    def list(
        self
    ):
        return self.spans
