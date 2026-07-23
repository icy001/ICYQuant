"""
Multi-agent collaboration coordinator.
"""


class CollaborationCoordinator:

    def __init__(
        self,
        scheduler,
        message_bus,
    ):

        self.scheduler = scheduler

        self.message_bus = message_bus

    def dispatch(self):

        task = self.scheduler.next()

        if task is None:

            return None

        self.message_bus.publish(task)

        return task