from decimal import Decimal

from services.portfolio import (
    BreachDetector,
    ComplianceRule,
    ComplianceViolation,
    ComplianceType,
    PortfolioLimitRule,
    LimitChecker,
    RiskRuleMonitor,
    PortfolioComplianceEngine,
    ComplianceService,
    ComplianceAlert,
)


def test_compliance_breach():
    detector = BreachDetector()

    rule = ComplianceRule(
        rule_id="R001",
        rule_name="risk_limit",
        limit_value=Decimal("100"),
    )

    result = detector.detect(rule, Decimal("150"))

    assert result is not None


def test_compliance_no_breach():
    detector = BreachDetector()

    rule = ComplianceRule(
        rule_id="R001",
        rule_name="risk_limit",
        limit_value=Decimal("100"),
    )

    result = detector.detect(rule, Decimal("80"))

    assert result is None


def test_compliance_violation():
    violation = ComplianceViolation(
        rule_id="R001",
        message="limit breached",
        actual_value=Decimal("150"),
        limit_value=Decimal("100"),
    )

    assert violation.rule_id == "R001"
    assert violation.message == "limit breached"
    assert violation.actual_value == Decimal("150")
    assert violation.limit_value == Decimal("100")


def test_compliance_type():
    assert ComplianceType.POSITION_LIMIT.value == "POSITION_LIMIT"
    assert ComplianceType.EXPOSURE_LIMIT.value == "EXPOSURE_LIMIT"
    assert ComplianceType.RISK_LIMIT.value == "RISK_LIMIT"
    assert ComplianceType.ALLOCATION_LIMIT.value == "ALLOCATION_LIMIT"


def test_portfolio_limit_rule():
    rule = PortfolioLimitRule(
        asset="AAPL",
        max_weight=Decimal("0.3"),
    )

    assert rule.asset == "AAPL"
    assert rule.max_weight == Decimal("0.3")


def test_limit_checker():
    checker = LimitChecker()
    rule = PortfolioLimitRule(
        asset="AAPL",
        max_weight=Decimal("0.3"),
    )

    assert checker.check("AAPL", Decimal("0.4"), rule)
    assert not checker.check("AAPL", Decimal("0.2"), rule)


def test_risk_rule_monitor():
    monitor = RiskRuleMonitor()

    assert monitor.check(Decimal("150"), Decimal("100"))
    assert not monitor.check(Decimal("80"), Decimal("100"))


def test_compliance_engine():
    detector = BreachDetector()
    engine = PortfolioComplianceEngine(detector)

    rules = [
        ComplianceRule(
            rule_id="R001",
            rule_name="risk_limit",
            limit_value=Decimal("100"),
        ),
        ComplianceRule(
            rule_id="R002",
            rule_name="exposure_limit",
            limit_value=Decimal("200"),
        ),
    ]

    values = {"R001": Decimal("150"), "R002": Decimal("180")}

    violations = engine.evaluate(rules, values)

    assert len(violations) == 1
    assert violations[0].rule_id == "R001"


def test_compliance_service():
    detector = BreachDetector()
    engine = PortfolioComplianceEngine(detector)
    service = ComplianceService(engine)

    rules = [
        ComplianceRule(
            rule_id="R001",
            rule_name="risk_limit",
            limit_value=Decimal("100"),
        ),
    ]

    values = {"R001": Decimal("150")}

    violations = service.monitor(rules, values)

    assert len(violations) == 1


def test_compliance_alert():
    alert = ComplianceAlert(
        severity="HIGH",
        message="risk limit breached",
    )

    assert alert.severity == "HIGH"
    assert alert.message == "risk limit breached"