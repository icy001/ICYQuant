class GatewayManager:
    def __init__(self, router, balancer):
        self.router = router
        self.balancer = balancer

    def route(self, path, instances):
        route = self.router.match(path)
        if not route:
            return None
        return self.balancer.choose(instances)
