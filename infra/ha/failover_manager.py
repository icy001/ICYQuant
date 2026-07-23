"""
High availability failover manager.
"""


class FailoverManager:

    def detect(
        self,
        service,
    ):
        return {
            "service":
                service,
            "status":
                "healthy"
        }

    def recover(
        self,
        service,
    ):
        return {
            "service":
                service,
            "action":
                "restart"
        }