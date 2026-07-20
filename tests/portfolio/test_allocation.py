from decimal import Decimal

import pytest

from services.portfolio import (
    AllocationTarget,
    AllocationSnapshot,
    AllocationValidator,
    RebalanceCalculator,
    AssetAllocationEngine,
    AllocationService,
)


def test_allocation_weight():
    validator = AllocationValidator()

    result = validator.validate(
        [
            AllocationTarget(
                asset_class="EQUITY",
                target_weight=Decimal("0.6"),
            ),
            AllocationTarget(
                asset_class="CASH",
                target_weight=Decimal("0.4"),
            ),
        ]
    )

    assert result is True


def test_allocation_weight_invalid():
    validator = AllocationValidator()

    result = validator.validate(
        [
            AllocationTarget(
                asset_class="EQUITY",
                target_weight=Decimal("0.7"),
            ),
            AllocationTarget(
                asset_class="CASH",
                target_weight=Decimal("0.4"),
            ),
        ]
    )

    assert result is False


def test_rebalance_calculator():
    calculator = RebalanceCalculator()

    diff = calculator.calculate(
        Decimal("0.5"),
        Decimal("0.6"),
    )

    assert diff == Decimal("0.1")


def test_allocation_engine():
    validator = AllocationValidator()
    rebalance = RebalanceCalculator()
    engine = AssetAllocationEngine(validator, rebalance)

    targets = [
        AllocationTarget(
            asset_class="EQUITY",
            target_weight=Decimal("0.6"),
        ),
        AllocationTarget(
            asset_class="BOND",
            target_weight=Decimal("0.3"),
        ),
        AllocationTarget(
            asset_class="CASH",
            target_weight=Decimal("0.1"),
        ),
    ]

    result = engine.allocate(targets, {"EQUITY": Decimal("0.5"), "BOND": Decimal("0.3")})

    assert len(result) == 3


def test_allocation_engine_invalid():
    validator = AllocationValidator()
    rebalance = RebalanceCalculator()
    engine = AssetAllocationEngine(validator, rebalance)

    targets = [
        AllocationTarget(
            asset_class="EQUITY",
            target_weight=Decimal("0.7"),
        ),
        AllocationTarget(
            asset_class="CASH",
            target_weight=Decimal("0.4"),
        ),
    ]

    with pytest.raises(ValueError, match="invalid allocation"):
        engine.allocate(targets, {})


def test_allocation_service():
    validator = AllocationValidator()
    rebalance = RebalanceCalculator()
    engine = AssetAllocationEngine(validator, rebalance)
    service = AllocationService(engine)

    targets = [
        AllocationTarget(
            asset_class="EQUITY",
            target_weight=Decimal("0.6"),
        ),
        AllocationTarget(
            asset_class="CASH",
            target_weight=Decimal("0.4"),
        ),
    ]

    result = service.calculate(targets, {"EQUITY": Decimal("0.5")})

    assert len(result) == 2


def test_allocation_snapshot():
    snapshot = AllocationSnapshot(
        asset_class="EQUITY",
        current_weight=Decimal("0.5"),
        target_weight=Decimal("0.6"),
    )

    assert snapshot.asset_class == "EQUITY"
    assert snapshot.current_weight == Decimal("0.5")
    assert snapshot.target_weight == Decimal("0.6")