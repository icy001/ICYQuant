"""
Central tracing manager.
"""


class TracingManager:

    def __init__(
        self,
        collector,
    ):
        self.collector = collector

    def record(
        self,
        span,
    ):
        self.collector.collect(
            span
        )