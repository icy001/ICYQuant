from services.backtest import (
    PositionLimitChecker,
    RiskRule,
    RiskResult,
    ExposureChecker,
    DrawdownGuard,
    BacktestRiskEngine,
    RiskService,
)


def test_position_limit():
    checker = PositionLimitChecker()

    rule = RiskRule(
        max_position=100,
        max_drawdown=0.2,
        max_exposure=1.0,
    )

    assert checker.check(50, rule)


def test_position_limit_exceeded():
    checker = PositionLimitChecker()

    rule = RiskRule(
        max_position=100,
        max_drawdown=0.2,
        max_exposure=1.0,
    )

    assert not checker.check(150, rule)


def test_risk_rule():
    rule = RiskRule(
        max_position=1000,
        max_drawdown=0.1,
        max_exposure=0.5,
    )

    assert rule.max_position == 1000
    assert rule.max_drawdown == 0.1
    assert rule.max_exposure == 0.5


def test_risk_result():
    approved = RiskResult(approved=True, reason=None)
    rejected = RiskResult(approved=False, reason="POSITION_LIMIT")

    assert approved.approved is True
    assert rejected.approved is False
    assert rejected.reason == "POSITION_LIMIT"


def test_exposure_checker():
    checker = ExposureChecker()

    rule = RiskRule(
        max_position=100,
        max_drawdown=0.2,
        max_exposure=0.5,
    )

    assert checker.check(0.3, rule)
    assert not checker.check(0.6, rule)


def test_drawdown_guard():
    guard = DrawdownGuard()

    rule = RiskRule(
        max_position=100,
        max_drawdown=0.2,
        max_exposure=1.0,
    )

    assert guard.check(0.1, rule)
    assert not guard.check(0.3, rule)


def test_risk_engine():
    position_checker = PositionLimitChecker()
    exposure_checker = ExposureChecker()
    drawdown_guard = DrawdownGuard()

    engine = BacktestRiskEngine(position_checker, exposure_checker, drawdown_guard)

    rule = RiskRule(
        max_position=100,
        max_drawdown=0.2,
        max_exposure=1.0,
    )

    class Order:
        quantity = 50

    class Portfolio:
        pass

    result = engine.evaluate(Order(), Portfolio(), rule)

    assert result.approved is True


def test_risk_engine_reject():
    position_checker = PositionLimitChecker()
    exposure_checker = ExposureChecker()
    drawdown_guard = DrawdownGuard()

    engine = BacktestRiskEngine(position_checker, exposure_checker, drawdown_guard)

    rule = RiskRule(
        max_position=100,
        max_drawdown=0.2,
        max_exposure=1.0,
    )

    class Order:
        quantity = 150

    class Portfolio:
        pass

    result = engine.evaluate(Order(), Portfolio(), rule)

    assert result.approved is False
    assert result.reason == "POSITION_LIMIT"


def test_risk_service():
    position_checker = PositionLimitChecker()
    exposure_checker = ExposureChecker()
    drawdown_guard = DrawdownGuard()

    engine = BacktestRiskEngine(position_checker, exposure_checker, drawdown_guard)
    service = RiskService(engine)

    rule = RiskRule(
        max_position=100,
        max_drawdown=0.2,
        max_exposure=1.0,
    )

    class Order:
        quantity = 80

    class Portfolio:
        pass

    result = service.check(Order(), Portfolio(), rule)

    assert result.approved is True