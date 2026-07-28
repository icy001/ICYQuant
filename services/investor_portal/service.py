class InvestorPortalService:
    def __init__(self, dashboard):
        self.dashboard = dashboard

    def open(self, data):
        return self.dashboard.view(data)
