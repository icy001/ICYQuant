"""
Multi agent collaboration.
"""


class AgentCollaboration:

    def __init__(self):

        self.agents = []

    def register(
        self,
        agent,
    ):

        self.agents.append(
            agent
        )

    def members(self):

        return self.agents