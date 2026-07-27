class RiskManager:
    def __init__(self, engine):
        self.engine = engine

    def check(self, exposure):
        return self.engine.evaluate(exposure)