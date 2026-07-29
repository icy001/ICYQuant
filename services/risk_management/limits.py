class DynamicRiskLimitEngine:
    def calculate(self, volatility):
        return {"limit": volatility}
