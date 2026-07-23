"""
Cross-agent knowledge sharing.
"""


class CrossAgentMemory:

    def __init__(self):

        self.shared = {}

    def publish(
        self,
        agent,
        knowledge,
    ):

        self.shared[agent] = knowledge

    def read(
        self,
        agent,
    ):

        return self.shared.get(agent)