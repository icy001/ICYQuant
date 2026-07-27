from services.compliance import *


def test_compliance_service():
    service = ComplianceService(
        ComplianceManager(
            ComplianceEngine(),
            ComplianceRepository()
        )
    )

    restriction = TradingRestriction(
        "NVDA",
        False,
        ""
    )

    result = service.check_trade(
        restriction
    )

    assert result.passed