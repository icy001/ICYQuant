class ComplianceService:
    def __init__(self, manager):
        self.manager = manager

    def check_trade(self, restriction):
        return self.manager.verify(restriction)