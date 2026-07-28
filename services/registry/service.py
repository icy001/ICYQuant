class ServiceRegistryService:
    def __init__(self, registration, discovery):
        self.registration = registration
        self.discovery = discovery

    def register(self, instance):
        return self.registration.register(instance)

    def discover(self, service_name):
        return self.discovery.discover(service_name)
