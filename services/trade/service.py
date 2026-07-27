class TradeService:
    def __init__(self, manager):
        self.manager = manager

    def confirm(self, trade):
        return self.manager.record(trade)