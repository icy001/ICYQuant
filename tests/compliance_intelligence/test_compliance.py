from services.compliance_intelligence import *


def test_trade_compliance():
    checker = TradeComplianceChecker()
    result = checker.validate({"symbol": "NVDA"})
    assert result["allowed"] is True


def test_rule_engine():
    engine = ComplianceRuleEngine()
    result = engine.check({"positions": [{"symbol": "AAPL", "weight": 0.15}]})
    assert result == {"approved": True}


def test_investment_mandate():
    manager = InvestmentMandateManager()
    rules = {"max_position": 0.10, "max_leverage": 2.0, "blocked": ["BCY"]}
    result = manager.create(rules)
    assert result == {"mandate": rules}


def test_trade_compliance_checker_approved():
    checker = TradeComplianceChecker()
    result = checker.validate({"symbol": "MSFT", "amount": 1000, "side": "buy"})
    assert result == {"allowed": True}


def test_regulatory_knowledge_engine():
    engine = RegulatoryKnowledgeEngine()
    result = engine.search("position limit regulation")
    assert result == {"result": "position limit regulation"}


def test_compliance_monitor_agent():
    agent = ComplianceMonitorAgent()
    result = agent.monitor({"positions": [], "orders": [], "exposure": 0.5})
    assert result == {"status": "normal"}


def test_regulatory_report_generator():
    generator = RegulatoryReportGenerator()
    result = generator.generate("monthly_exposure_report")
    assert result == {"report": "monthly_exposure_report"}


def test_compliance_alert_system():
    alert_system = ComplianceAlertSystem()
    result = alert_system.alert("Position limit breach: AAPL at 12%")
    assert result == {"alert": "Position limit breach: AAPL at 12%"}


def test_audit_trail_engine():
    audit = AuditTrailEngine()
    assert audit.logs == []
    audit.record({"event": "order_validated", "order_id": "ORD-001", "result": "approved"})
    audit.record({"event": "compliance_check", "check_id": "CHK-001", "result": "passed"})
    assert len(audit.logs) == 2
    assert audit.logs[0]["event"] == "order_validated"
    assert audit.logs[1]["event"] == "compliance_check"


def test_compliance_risk_scoring():
    scoring = ComplianceRiskScoring()
    result = scoring.score({"violations": 0, "warnings": 1})
    assert result == 100


def test_compliance_memory():
    memory = ComplianceMemory()
    assert memory.history == []
    memory.save({"violation": "position_limit", "date": "2024-06-01"})
    memory.save({"regulation": "SEC_Rule_101", "update": "amended"})
    assert len(memory.history) == 2
    assert memory.history[0]["violation"] == "position_limit"
    assert memory.history[1]["regulation"] == "SEC_Rule_101"


def test_compliance_intelligence_service():
    checker = TradeComplianceChecker()
    service = ComplianceIntelligenceService(checker=checker)
    result = service.validate({"symbol": "GOOGL", "amount": 500})
    assert result == {"allowed": True}


def test_full_compliance_workflow():
    """End-to-end compliance intelligence workflow."""
    # 1. Create investment mandate
    mandate_mgr = InvestmentMandateManager()
    mandate = mandate_mgr.create({
        "max_single_position": 0.10,
        "max_leverage": 2.5,
        "blocked_securities": [],
        "risk_limit": "10% VaR",
    })
    assert mandate["mandate"]["max_single_position"] == 0.10

    # 2. Check portfolio against rules
    rule_engine = ComplianceRuleEngine()
    portfolio_check = rule_engine.check({
        "positions": [{"symbol": "NVDA", "weight": 0.08}],
    })
    assert portfolio_check["approved"] is True

    # 3. Validate trade
    trade_checker = TradeComplianceChecker()
    trade_result = trade_checker.validate({"symbol": "NVDA", "amount": 2000, "side": "buy"})
    assert trade_result["allowed"] is True

    # 4. Search regulatory knowledge
    reg_engine = RegulatoryKnowledgeEngine()
    reg_result = reg_engine.search("Regulation T margin requirements")
    assert reg_result["result"] == "Regulation T margin requirements"

    # 5. Monitor compliance
    monitor = ComplianceMonitorAgent()
    monitor_result = monitor.monitor({"exposure": 1.2, "num_positions": 25})
    assert monitor_result["status"] == "normal"

    # 6. Generate regulatory report
    report_gen = RegulatoryReportGenerator()
    report = report_gen.generate("quarterly_compliance_report")
    assert report["report"] == "quarterly_compliance_report"

    # 7. Send alert
    alert_system = ComplianceAlertSystem()
    alert = alert_system.alert("Margin utilization approaching limit: 85%")
    assert alert["alert"] == "Margin utilization approaching limit: 85%"

    # 8. Record audit trail
    audit = AuditTrailEngine()
    audit.record({"action": "trade_approved", "order": "ORD-100"})
    audit.record({"action": "mandate_created", "mandate_id": "MND-001"})
    assert len(audit.logs) == 2

    # 9. Score compliance health
    scoring = ComplianceRiskScoring()
    score = scoring.score({"violations": 0, "audits_completed": 5})
    assert score == 100

    # 10. Save to compliance memory
    memory = ComplianceMemory()
    memory.save({"event": "full_audit_completed", "date": "2024-Q3"})
    assert len(memory.history) == 1

    # 11. Compliance service
    service = ComplianceIntelligenceService(checker=trade_checker)
    service_result = service.validate({"symbol": "AMD", "amount": 1500})
    assert service_result["allowed"] is True
