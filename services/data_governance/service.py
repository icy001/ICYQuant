class DataGovernanceService:
    def __init__(self, quality):
        self.quality = quality

    def check(self, dataset):
        return self.quality.check(dataset)
