from .result import DiscoveryResult


class DiscoveryEngine:
    def __init__(self, repository):
        self.repository = repository

    def discover(self, service_name):
        instances = self.repository.find(service_name)
        return DiscoveryResult(service_name, instances)
