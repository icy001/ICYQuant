class FundAdministratorService:
    def __init__(self, nav):
        self.nav = nav

    def calculate_nav(self, assets, liabilities):
        return self.nav.calculate(assets, liabilities)
