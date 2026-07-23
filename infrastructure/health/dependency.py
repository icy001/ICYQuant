"""
External dependency monitoring.
"""


class DependencyMonitor:

    def check(
        self,
        dependency,
    ):
        return {
            "dependency":
                dependency,
            "available":
                True
        }