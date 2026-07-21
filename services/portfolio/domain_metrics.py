"""
Domain metrics.
"""


class DomainMetrics:

    def collect(
        self,
        registry,
    ):

        return {
            "modules":
                len(
                    registry.modules
                )
        }