"""
Fault tolerance manager.
"""


class FaultToleranceManager:

    def recover(
        self,
        task,
        failed_node,
    ):

        return {
            "task": task,
            "retry": True,
            "failed_node": failed_node,
        }