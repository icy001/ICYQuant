from decimal import Decimal

import pytest

from services.portfolio import (
    CapitalPool,
    CapitalValidator,
    CapitalAllocationEngine,
    CapitalService,
    CapitalSnapshot,
    CapitalAllocation,
)


def test_capital_available():
    pool = CapitalPool(
        total_capital=Decimal("100000"),
        allocated_capital=Decimal("30000"),
    )

    validator = CapitalValidator()

    assert validator.validate(pool, Decimal("50000"))


def test_capital_insufficient():
    pool = CapitalPool(
        total_capital=Decimal("100000"),
        allocated_capital=Decimal("80000"),
    )

    validator = CapitalValidator()

    assert not validator.validate(pool, Decimal("30000"))


def test_capital_pool_available():
    pool = CapitalPool(
        total_capital=Decimal("100000"),
        allocated_capital=Decimal("30000"),
    )

    assert pool.available() == Decimal("70000")


def test_capital_allocation_engine():
    validator = CapitalValidator()
    engine = CapitalAllocationEngine(validator)

    pool = CapitalPool(
        total_capital=Decimal("100000"),
        allocated_capital=Decimal("0"),
    )

    result = engine.allocate(pool, "strategy-001", Decimal("50000"))

    assert result["strategy_id"] == "strategy-001"
    assert result["allocated"] == Decimal("50000")
    assert pool.allocated_capital == Decimal("50000")


def test_capital_allocation_engine_insufficient():
    validator = CapitalValidator()
    engine = CapitalAllocationEngine(validator)

    pool = CapitalPool(
        total_capital=Decimal("100000"),
        allocated_capital=Decimal("80000"),
    )

    with pytest.raises(ValueError, match="insufficient capital"):
        engine.allocate(pool, "strategy-001", Decimal("30000"))


def test_capital_service():
    validator = CapitalValidator()
    engine = CapitalAllocationEngine(validator)
    service = CapitalService(engine)

    pool = CapitalPool(
        total_capital=Decimal("100000"),
        allocated_capital=Decimal("0"),
    )

    result = service.allocate(pool, "strategy-001", Decimal("30000"))

    assert result["strategy_id"] == "strategy-001"
    assert pool.allocated_capital == Decimal("30000")


def test_capital_snapshot():
    snapshot = CapitalSnapshot(
        total=Decimal("100000"),
        allocated=Decimal("30000"),
        available=Decimal("70000"),
    )

    assert snapshot.total == Decimal("100000")
    assert snapshot.allocated == Decimal("30000")
    assert snapshot.available == Decimal("70000")


def test_capital_allocation():
    allocation = CapitalAllocation(
        strategy_id="strategy-001",
        allocated_capital=Decimal("50000"),
        reserved_capital=Decimal("10000"),
    )

    assert allocation.strategy_id == "strategy-001"
    assert allocation.allocated_capital == Decimal("50000")
    assert allocation.reserved_capital == Decimal("10000")