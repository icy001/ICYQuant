"""
Agent execution service.
"""


class AgentExecutionService:

    def __init__(
        self,
        runtime,
        memory,
    ):

        self.runtime = runtime

        self.memory = memory

    def execute(
        self,
        task,
    ):

        context = self.memory.context(
            task.objective
        )

        result = self.runtime.run(
            task.objective
        )

        return {
            "context": context,
            "result": result,
        }