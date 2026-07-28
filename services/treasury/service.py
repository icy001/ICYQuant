class TreasuryService:
    def __init__(self, cash_manager):
        self.cash_manager = cash_manager

    def position(self, account):
        return self.cash_manager.get_position(account)
