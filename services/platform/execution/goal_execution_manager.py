"""
Goal execution manager.
"""


class GoalExecutionManager:

    def __init__(self):

        self.tasks = []

    def submit(
        self,
        task,
    ):

        self.tasks.append(task)

    def pending(self):

        return self.tasks