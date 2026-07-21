"""
Portfolio query gateway.
"""

from .query_response import QueryResponse


class PortfolioQueryGateway:

    def __init__(
        self,
        router,
        authorizer,
        aggregator,
    ):

        self.router = router

        self.authorizer = authorizer

        self.aggregator = aggregator

    def query(
        self,
        user,
        request,
        service,
    ):

        if not self.authorizer.authorize(
            user,
            request,
        ):

            raise PermissionError(
                "Unauthorized"
            )

        result = self.router.route(
            request,
            service,
        )

        return QueryResponse(
            success=True,
            data=self.aggregator.aggregate(
                result,
            ),
        )