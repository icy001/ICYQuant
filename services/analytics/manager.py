class AnalyticsManager:
    def __init__(self, repository, calculator):
        self.repository = repository
        self.calculator = calculator

    def calculate_performance(self, initial, final):
        value = self.calculator.calculate_return(
            initial,
            final
        )

        self.repository.save(
            "return",
            value
        )

        return value