"""
Internal RPC client abstraction.
"""


class RPCClient:

    def __init__(
        self,
        registry,
    ):
        self.registry = registry

    def call(
        self,
        service,
        request,
    ):
        instances = self.registry.get(service)

        if not instances:
            return None

        return {
            "service":
                service,
            "request":
                request
        }