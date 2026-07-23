"""
Trace processing pipeline.
"""


class TracePipeline:

    def __init__(self):
        self.events = []

    def publish(
        self,
        span,
    ):
        self.events.append(span)