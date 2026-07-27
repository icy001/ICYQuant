class ComplianceManager:
    def __init__(self, engine, repository):
        self.engine = engine
        self.repository = repository

    def verify(self, restriction):
        return self.engine.check(restriction)