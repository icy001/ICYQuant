class MeshRegistry:

    def __init__(self):
        self.services = {}

    def register(
        self,
        endpoint
    ):
        self.services[endpoint.name] = endpoint

    def discover(
        self,
        name
    ):
        return self.services.get(name)
