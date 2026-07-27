from services.analytics import *


def test_performance():
    service = AnalyticsService(
        AnalyticsManager(
            AnalyticsRepository(),
            PerformanceCalculator()
        )
    )

    result = service.performance(
        100000,
        110000
    )

    assert result == 0.1