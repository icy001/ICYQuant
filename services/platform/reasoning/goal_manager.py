"""
Goal manager.
"""


class GoalManager:

    def __init__(self):

        self.goals = {}

    def register(self, goal):

        self.goals[goal.goal_id] = goal

    def get(self, goal_id):

        return self.goals.get(goal_id)

    def list(self):

        return list(self.goals.values())