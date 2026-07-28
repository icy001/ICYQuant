from .result import OptimizationResult


class OptimizationManager:
    def __init__(self, allocator, repository):
        self.allocator = allocator
        self.repository = repository

    def optimize(self, request):
        weights = self.allocator.optimize(request.assets)

        result = OptimizationResult(
            request.portfolio_id,
            weights,
            0.0,
            0.0
        )

        self.repository.save(result)

        return result