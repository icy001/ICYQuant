class OptimizationService:
    def __init__(self, manager):
        self.manager = manager

    def optimize(self, request):
        return self.manager.optimize(request)