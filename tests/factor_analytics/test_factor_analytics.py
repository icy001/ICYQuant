from services.factor_analytics import *


def test_factor_analysis():

    repo = FactorAnalyticsRepository()

    service = FactorAnalyticsService(repo)

    performance = FactorPerformance(

        "MOM001",

        0.15,

        0.2,

        1.5

    )

    service.record(performance)

    result = service.history()

    assert result[0].factor_id == "MOM001"
