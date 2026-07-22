"""
Platform health.
"""


class PlatformHealth:

    def check(
        self,
        registry,
    ):

        return {
            "registered_services":
                len(registry._services),
            "healthy": True,
        }