"""
Failover manager.
"""


class FailoverManager:
    def activate(
        self,
        standby_node,
    ):
        return {
            "active_node": standby_node,
        }