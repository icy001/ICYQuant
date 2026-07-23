"""
Central logging manager.
"""


class LogManager:

    def __init__(
        self,
        pipeline,
        storage,
    ):
        self.pipeline = pipeline
        self.storage = storage

    def write(
        self,
        event,
    ):
        self.pipeline.publish(event)
        self.storage.save(event)