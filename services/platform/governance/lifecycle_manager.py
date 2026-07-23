"""
Agent lifecycle manager.
"""


class LifecycleManager:

    def __init__(self):

        self.status = {}

    def update(self, agent_id, state):

        self.status[agent_id] = state

    def get(self, agent_id):

        return self.status.get(agent_id)