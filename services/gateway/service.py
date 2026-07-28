class GatewayService:
    def __init__(self, manager):
        self.manager = manager

    def forward(self, path, instances):
        return self.manager.route(path, instances)
