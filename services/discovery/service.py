from .health import HealthChecker


class DiscoveryService:
    def __init__(self, repository):
        self.repository = repository
        self.health = HealthChecker()

    def register(self, instance):
        self.repository.save(instance)
        return instance

    def healthy(self, instance):
        return self.health.check(instance)
