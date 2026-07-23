"""
Agent governance center.
"""


class GovernanceCenter:

    def __init__(
        self,
        lifecycle,
        monitor,
        metrics,
    ):

        self.lifecycle = lifecycle

        self.monitor = monitor

        self.metrics = metrics

    def overview(self):

        return {
            "status": "healthy",
            "agents": len(
                self.lifecycle.status
            ),
        }