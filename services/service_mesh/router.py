class RoutingController:

    def route(
        self,
        endpoint
    ):
        if endpoint.healthy:
            return endpoint

        return None
