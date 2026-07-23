"""
Saga coordinator.
"""


class SagaCoordinator:

    def __init__(self):

        self.completed = []

    def commit(
        self,
        step,
    ):

        self.completed.append(step)

    def rollback(self):

        return list(
            reversed(
                self.completed
            )
        )