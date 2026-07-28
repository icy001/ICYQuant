class LoadBalancer:
    def __init__(self, strategy, health_filter):
        self.strategy = strategy
        self.health_filter = health_filter

    def choose(self, instances):
        healthy = self.health_filter.filter(instances)
        return self.strategy.select(healthy)
