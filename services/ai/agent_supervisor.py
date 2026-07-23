"""
AI Agent Supervisor.
"""


class AgentSupervisor:

    def __init__(
        self,
        registry,
    ):

        self.registry = registry

    def dispatch(
        self,
        task_type,
        payload,
    ):

        agent = self.registry.get(
            task_type
        )

        if agent is None:

            raise ValueError(
                "Agent not found"
            )

        return agent.analyze(
            payload
        )