class AllocationEngine:
    def optimize(self, assets):
        count = len(assets)

        if count == 0:
            return []

        weight = 1 / count

        return [
            {
                "symbol": asset,
                "weight": weight
            }
            for asset in assets
        ]