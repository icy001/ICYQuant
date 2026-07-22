"""
Streaming publisher.
"""


class StreamPublisher:

    def __init__(
        self,
        stream,
    ):

        self.stream = stream

    def publish(
        self,
        tick,
    ):

        self.stream.publish(
            tick
        )