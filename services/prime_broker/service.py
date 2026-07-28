class PrimeBrokerService:
    def __init__(self, adapter):
        self.adapter = adapter

    def connect(self, broker):
        return self.adapter.connect(broker)
