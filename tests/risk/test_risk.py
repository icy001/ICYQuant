from services.risk.exposure import SimpleExposure
from services.risk.engine import SimpleRiskEngine
from services.risk.manager import RiskManager
from services.risk.pre_trade_service_v2 import RiskService


def test_risk_engine():
    exposure = SimpleExposure(
        symbol="NVDA",
        value=80000,
        limit=100000
    )

    service = RiskService(
        RiskManager(
            SimpleRiskEngine()
        )
    )

    result = service.pre_trade_check(
        exposure
    )

    assert result.passed