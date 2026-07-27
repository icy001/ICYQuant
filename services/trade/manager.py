class TradeManager:
    def __init__(self, repository, publisher):
        self.repository = repository
        self.publisher = publisher

    def record(self, trade):
        self.repository.save(trade)

        self.publisher.publish_trade(trade)

        return trade