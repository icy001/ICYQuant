class ServiceMeshService:

    def __init__(
        self,
        registry,
        router,
        security
    ):
        self.registry = registry
        self.router = router
        self.security = security

    def connect(
        self,
        service_name
    ):
        endpoint = self.registry.discover(
            service_name
        )

        return self.router.route(
            endpoint
        )
