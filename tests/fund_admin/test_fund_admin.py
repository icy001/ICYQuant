from services.fund_admin import *


def test_nav_admin():
    nav = NAVAdministrator()
    result = nav.calculate(10_000_000, 2_000_000)
    assert result == 8_000_000


def test_fund_lifecycle_create():
    manager = FundLifecycleManager()
    result = manager.create("ICY Alpha Fund")
    assert result == {"fund": "ICY Alpha Fund", "status": "created"}


def test_fund_status_enum():
    assert FundStatus.CREATED.value == "created"
    assert FundStatus.ACTIVE.value == "active"
    assert FundStatus.CLOSED.value == "closed"


def test_nav_validation_valid():
    engine = NAVValidationEngine()
    result = engine.validate(8_000_000)
    assert result == {"valid": True}


def test_nav_validation_invalid():
    engine = NAVValidationEngine()
    result = engine.validate(-100_000)
    assert result == {"valid": False}


def test_nav_validation_zero():
    engine = NAVValidationEngine()
    result = engine.validate(0)
    assert result == {"valid": True}


def test_reconciliation_matched():
    engine = FundReconciliationEngine()
    result = engine.reconcile(5_000_000, 5_000_000)
    assert result == {"matched": True}


def test_reconciliation_mismatched():
    engine = FundReconciliationEngine()
    result = engine.reconcile(5_000_000, 5_000_100)
    assert result == {"matched": False}


def test_fee_calculation():
    engine = FeeCalculationEngine()
    fee = engine.management_fee(10_000_000, 0.02)
    assert fee == 200_000


def test_investor_data_register():
    manager = InvestorDataManager()
    result = manager.register("LP_Alpha")
    assert result == {"investor": "LP_Alpha"}


def test_compliance_document_generate():
    generator = ComplianceDocumentGenerator()
    result = generator.generate("monthly_statement")
    assert result == {"document": "monthly_statement"}


def test_operational_workflow():
    engine = OperationalWorkflowEngine()
    result = engine.execute("trade_settlement")
    assert result == {"workflow": "trade_settlement", "status": "completed"}


def test_exception_manager():
    manager = ExceptionManager()
    result = manager.create("NAV mismatch detected")
    assert result == {"issue": "NAV mismatch detected", "status": "open"}


def test_administrator_memory():
    memory = AdministratorMemory()
    assert memory.records == []
    memory.save({"operation": "nav_calculation", "result": "success"})
    memory.save({"operation": "reconciliation", "result": "matched"})
    assert len(memory.records) == 2
    assert memory.records[0] == {"operation": "nav_calculation", "result": "success"}
    assert memory.records[1] == {"operation": "reconciliation", "result": "matched"}


def test_fund_admin_service():
    nav = NAVAdministrator()
    service = FundAdministratorService(nav=nav)
    result = service.calculate_nav(15_000_000, 3_000_000)
    assert result == 12_000_000


def test_full_fund_admin_workflow():
    """End-to-end fund administration workflow."""
    # 1. Create fund
    lifecycle = FundLifecycleManager()
    fund = lifecycle.create("ICY Macro Fund")
    assert fund["status"] == "created"

    # 2. Calculate NAV
    nav_admin = NAVAdministrator()
    nav = nav_admin.calculate(50_000_000, 10_000_000)
    assert nav == 40_000_000

    # 3. Validate NAV
    validator = NAVValidationEngine()
    validation = validator.validate(nav)
    assert validation["valid"] is True

    # 4. Reconcile positions
    reconciler = FundReconciliationEngine()
    recon = reconciler.reconcile(40_000_000, 40_000_000)
    assert recon["matched"] is True

    # 5. Calculate fees
    fee_engine = FeeCalculationEngine()
    mgmt_fee = fee_engine.management_fee(40_000_000, 0.02)
    assert mgmt_fee == 800_000

    # 6. Register investor
    investor_mgr = InvestorDataManager()
    investor = investor_mgr.register("LP_Omega")
    assert investor["investor"] == "LP_Omega"

    # 7. Generate compliance document
    doc_gen = ComplianceDocumentGenerator()
    doc = doc_gen.generate("quarterly_report")
    assert doc["document"] == "quarterly_report"

    # 8. Execute workflow
    workflow = OperationalWorkflowEngine()
    wf_result = workflow.execute("monthly_close")
    assert wf_result["status"] == "completed"

    # 9. Handle exception
    exception_mgr = ExceptionManager()
    exception = exception_mgr.create("Fee calculation discrepancy")
    assert exception["status"] == "open"

    # 10. Save to memory
    memory = AdministratorMemory()
    memory.save({"event": "fund_launch", "fund": "ICY Macro Fund"})
    memory.save({"event": "nav_calculated", "nav": 40_000_000})
    assert len(memory.records) == 2

    # 11. Fund administrator service
    service = FundAdministratorService(nav=nav_admin)
    service_nav = service.calculate_nav(60_000_000, 15_000_000)
    assert service_nav == 45_000_000
