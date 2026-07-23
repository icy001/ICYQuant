"""
Runtime service routing.
"""


class ServiceRouter:

    def route(
        self,
        instances,
    ):
        if not instances:
            return None

        return instances[0]