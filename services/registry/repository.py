class ServiceRepository:
    def __init__(self):
        self.services = {}

    def save(self, instance):
        self.services.setdefault(instance.service_name, []).append(instance)

    def find(self, service_name):
        return self.services.get(service_name, [])
