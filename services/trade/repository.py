class TradeRepository:
    def __init__(self):
        self.trades = {}

    def save(self, trade):
        self.trades[trade.trade_id] = trade

    def find(self, trade_id):
        return self.trades.get(trade_id)