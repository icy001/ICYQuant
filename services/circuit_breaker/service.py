class CircuitBreakerService:
    def __init__(self, manager):
        self.manager = manager

    def failure(self, record, config):
        return self.manager.record_failure(record, config)

    def recover(self):
        return self.manager.recover()
