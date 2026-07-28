class RecoveryService:
    def __init__(self, manager):
        self.manager = manager

    def recover(self, request):
        return self.manager.recover(request)