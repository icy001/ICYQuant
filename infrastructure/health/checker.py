"""
Service health checker.
"""


class HealthChecker:

    def check(
        self,
        service,
    ):
        return {
            "service":
                service,
            "status":
                "healthy"
        }