from services.prime_broker import *


def test_broker_connection():
    adapter = PrimeBrokerAdapter()
    result = adapter.connect("PrimeBroker")
    assert result["status"] == "connected"


def test_broker_account_create():
    manager = BrokerAccountManager()
    result = manager.create("ACCT-001")
    assert result == {"account": "ACCT-001"}


def test_margin_calculation():
    engine = MarginManagementEngine()
    result = engine.calculate(1_000_000, 300_000)
    assert result == 700_000


def test_financing_cost():
    engine = FinancingCostEngine()
    result = engine.calculate(500_000, 0.05)
    assert result == 25_000


def test_securities_lending():
    interface = SecuritiesLendingInterface()
    result = interface.borrow("NVDA")
    assert result == {"symbol": "NVDA", "available": True}


def test_collateral_value():
    engine = CollateralManagementEngine()
    result = engine.value([100_000, 50_000, 25_000])
    assert result == 175_000


def test_broker_reconciliation_matched():
    engine = BrokerReconciliationEngine()
    result = engine.reconcile(5_000_000, 5_000_000)
    assert result == {"matched": True}


def test_broker_reconciliation_mismatched():
    engine = BrokerReconciliationEngine()
    result = engine.reconcile(5_000_000, 5_000_500)
    assert result == {"matched": False}


def test_broker_risk_monitor():
    monitor = BrokerRiskMonitor()
    result = monitor.check({"exposure": 0.8})
    assert result == {"risk": "normal"}


def test_settlement_manager():
    manager = SettlementManager()
    result = manager.settle("TRD-001")
    assert result == {"trade": "TRD-001", "status": "settled"}


def test_prime_broker_memory():
    memory = PrimeBrokerMemory()
    assert memory.history == []
    memory.save({"event": "broker_connected", "broker": "PB-01"})
    memory.save({"event": "trade_settled", "trade_id": "TRD-001"})
    assert len(memory.history) == 2
    assert memory.history[0]["event"] == "broker_connected"
    assert memory.history[1]["event"] == "trade_settled"


def test_prime_broker_service():
    adapter = PrimeBrokerAdapter()
    service = PrimeBrokerService(adapter=adapter)
    result = service.connect("GoldmanSachs_PB")
    assert result == {"broker": "GoldmanSachs_PB", "status": "connected"}


def test_full_prime_broker_workflow():
    """End-to-end prime brokerage workflow."""
    # 1. Connect to broker
    adapter = PrimeBrokerAdapter()
    connection = adapter.connect("MorganStanley_PB")
    assert connection["status"] == "connected"

    # 2. Create broker account
    account_mgr = BrokerAccountManager()
    account = account_mgr.create("ACCT-ALPHA-01")
    assert account["account"] == "ACCT-ALPHA-01"

    # 3. Check margin
    margin_engine = MarginManagementEngine()
    available = margin_engine.calculate(10_000_000, 2_500_000)
    assert available == 7_500_000

    # 4. Calculate financing cost
    financing = FinancingCostEngine()
    cost = financing.calculate(2_000_000, 0.04)
    assert cost == 80_000

    # 5. Borrow securities
    lending = SecuritiesLendingInterface()
    borrow = lending.borrow("AAPL")
    assert borrow["available"] is True

    # 6. Evaluate collateral
    collateral = CollateralManagementEngine()
    total = collateral.value([1_000_000, 500_000, 250_000])
    assert total == 1_750_000

    # 7. Reconcile positions
    reconciler = BrokerReconciliationEngine()
    recon = reconciler.reconcile(10_000_000, 10_000_000)
    assert recon["matched"] is True

    # 8. Monitor broker risk
    risk_monitor = BrokerRiskMonitor()
    risk = risk_monitor.check({"leverage": 1.5, "margin_util": 0.35})
    assert risk["risk"] == "normal"

    # 9. Settle trades
    settlement = SettlementManager()
    settled = settlement.settle("TRD-ALPHA-100")
    assert settled["status"] == "settled"

    # 10. Save broker events
    memory = PrimeBrokerMemory()
    memory.save({"event": "connection_established", "broker": "MorganStanley_PB"})
    memory.save({"event": "trade_settled", "trade": "TRD-ALPHA-100"})
    assert len(memory.history) == 2

    # 11. Prime broker service
    service = PrimeBrokerService(adapter=adapter)
    svc_result = service.connect("GoldmanSachs_PB")
    assert svc_result["status"] == "connected"
