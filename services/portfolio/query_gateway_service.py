"""
Query gateway service.
"""


class QueryGatewayService:

    def __init__(
        self,
        gateway,
    ):

        self.gateway = gateway

    def query(
        self,
        *args,
        **kwargs,
    ):

        return self.gateway.query(
            *args,
            **kwargs,
        )