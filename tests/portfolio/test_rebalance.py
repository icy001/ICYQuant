from decimal import Decimal

from services.portfolio import (
    DriftDetector,
    RebalancePolicy,
    RebalanceEngine,
    RebalanceOrderGenerator,
    RebalanceService,
    RebalanceRequest,
)


def test_drift():
    detector = DriftDetector()

    result = detector.calculate(
        Decimal("0.4"),
        Decimal("0.6"),
    )

    assert result == Decimal("0.2")


def test_drift_negative():
    detector = DriftDetector()

    result = detector.calculate(
        Decimal("0.7"),
        Decimal("0.5"),
    )

    assert result == Decimal("-0.2")


def test_exceed_threshold():
    detector = DriftDetector()

    assert detector.exceed_threshold(Decimal("0.05"), Decimal("0.05"))
    assert detector.exceed_threshold(Decimal("0.1"), Decimal("0.05"))
    assert not detector.exceed_threshold(Decimal("0.04"), Decimal("0.05"))


def test_rebalance_policy():
    policy = RebalancePolicy(threshold=Decimal("0.05"))

    assert policy.threshold == Decimal("0.05")


def test_rebalance_engine():
    detector = DriftDetector()
    policy = RebalancePolicy(threshold=Decimal("0.05"))
    engine = RebalanceEngine(detector, policy)

    current = {"AAPL": Decimal("0.4"), "MSFT": Decimal("0.6")}
    target = {"AAPL": Decimal("0.6"), "MSFT": Decimal("0.4")}

    requests = engine.evaluate(current, target)

    assert len(requests) == 2


def test_rebalance_engine_no_drift():
    detector = DriftDetector()
    policy = RebalancePolicy(threshold=Decimal("0.05"))
    engine = RebalanceEngine(detector, policy)

    current = {"AAPL": Decimal("0.5"), "MSFT": Decimal("0.5")}
    target = {"AAPL": Decimal("0.5"), "MSFT": Decimal("0.5")}

    requests = engine.evaluate(current, target)

    assert len(requests) == 0


def test_order_generator():
    generator = RebalanceOrderGenerator()

    requests = [
        RebalanceRequest(
            asset="AAPL",
            current_weight=Decimal("0.4"),
            target_weight=Decimal("0.6"),
            delta=Decimal("0.2"),
        ),
        RebalanceRequest(
            asset="MSFT",
            current_weight=Decimal("0.6"),
            target_weight=Decimal("0.4"),
            delta=Decimal("-0.2"),
        ),
    ]

    orders = generator.generate(requests)

    assert len(orders) == 2
    assert orders[0]["direction"] == "BUY"
    assert orders[1]["direction"] == "SELL"


def test_rebalance_service():
    detector = DriftDetector()
    policy = RebalancePolicy(threshold=Decimal("0.05"))
    engine = RebalanceEngine(detector, policy)
    generator = RebalanceOrderGenerator()
    service = RebalanceService(engine, generator)

    current = {"AAPL": Decimal("0.4"), "MSFT": Decimal("0.6")}
    target = {"AAPL": Decimal("0.6"), "MSFT": Decimal("0.4")}

    orders = service.rebalance(current, target)

    assert len(orders) == 2


def test_rebalance_request():
    request = RebalanceRequest(
        asset="AAPL",
        current_weight=Decimal("0.4"),
        target_weight=Decimal("0.6"),
        delta=Decimal("0.2"),
    )

    assert request.asset == "AAPL"
    assert request.current_weight == Decimal("0.4")
    assert request.target_weight == Decimal("0.6")
    assert request.delta == Decimal("0.2")