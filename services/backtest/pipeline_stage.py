"""
Pipeline stage.
"""


class PipelineStage:

    def __init__(
        self,
        name,
        handler,
    ):

        self.name = name

        self.handler = handler


    def execute(
        self,
        context,
    ):

        return self.handler(
            context
        )