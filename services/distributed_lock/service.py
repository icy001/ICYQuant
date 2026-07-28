class DistributedLockService:
    def __init__(self, coordinator):
        self.coordinator = coordinator

    def execute(self, request, action):
        return self.coordinator.execute(request, action)
