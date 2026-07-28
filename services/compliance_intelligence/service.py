class ComplianceIntelligenceService:
    def __init__(self, checker):
        self.checker = checker

    def validate(self, order):
        return self.checker.validate(order)
