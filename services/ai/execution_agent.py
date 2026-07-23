"""
Execution Intelligence Agent.
"""


class ExecutionAgent:

    def __init__(
        self,
        ai_service,
    ):

        self.ai_service = ai_service

    def analyze(
        self,
        execution_context,
    ):

        prompt = f"""
        Optimize execution strategy.

        {execution_context}

        """

        return self.ai_service.execute(
            prompt
        )