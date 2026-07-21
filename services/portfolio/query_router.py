"""
Query router.
"""


class QueryRouter:

    def route(
        self,
        request,
        service,
    ):

        return service.get(
            request.portfolio_id,
        )