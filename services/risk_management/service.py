class RiskManagementService:
    def __init__(self, monitor):
        self.monitor = monitor

    def check(self, portfolio):
        return self.monitor.monitor(portfolio)
