from services.platform.fund import (
    FundLifecycleManager,
)


def test_fund_status():

    manager = FundLifecycleManager()

    assert manager.status() == "ACTIVE"