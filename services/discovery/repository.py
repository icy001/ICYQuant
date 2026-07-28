from .registry import ServiceRegistry


class DiscoveryRepository:
    def __init__(self):
        self.registry = ServiceRegistry()

    def save(self, instance):
        self.registry.register(instance)

    def remove(self, instance_id):
        self.registry.unregister(instance_id)
