"""
Multi-agent runtime.
"""


class MultiAgentRuntime:

    def __init__(
        self,
        coordinator,
        registry,
    ):

        self.coordinator = coordinator

        self.registry = registry

    def execute(self):

        return self.coordinator.dispatch()