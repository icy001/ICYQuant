class PortfolioConstructionService:
    def __init__(self, allocator):
        self.allocator = allocator

    def build(self, assets):
        return self.allocator.allocate(assets)
