class AnalyticsService:
    def __init__(self, manager):
        self.manager = manager

    def performance(self, initial, final):
        return self.manager.calculate_performance(
            initial,
            final
        )