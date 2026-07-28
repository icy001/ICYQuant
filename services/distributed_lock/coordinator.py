class LockCoordinator:
    def __init__(self, manager):
        self.manager = manager

    def execute(self, request, action):
        acquired = self.manager.acquire(request)

        if not acquired:
            return None

        try:
            return action()
        finally:
            self.manager.release(request.resource)
