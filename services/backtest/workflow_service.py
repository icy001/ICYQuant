"""
Workflow service.
"""


class WorkflowService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine


    def execute(
        self,
        workflow,
        context,
    ):

        return self.engine.run(
            workflow,
            context,
        )