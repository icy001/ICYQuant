"""Tests for Capital Allocator."""

import pytest
from services.portfolio_management.capital_allocator import (
    CapitalAllocator, CapitalPool, AllocationRule, AllocationRequest,
    AllocationResult, AllocationMethod, CapitalFlow,
)


class TestCapitalAllocator:
    """Test capital allocation engine."""

    @pytest.fixture
    def allocator(self):
        return CapitalAllocator()

    @pytest.fixture
    def pool(self, allocator):
        return allocator.create_pool("Main Pool", 100_000_000)

    def test_create_pool(self, allocator):
        pool = allocator.create_pool("Test Pool", 50_000_000, "CNY")
        assert pool.name == "Test Pool"
        assert pool.total_capital == 50_000_000
        assert pool.available_capital == 50_000_000
        assert pool.utilization_pct == 0.0

    def test_equal_weight_allocation(self, allocator, pool):
        rules = [
            AllocationRule(name="Portfolio A", target_id="p1", min_allocation=0, max_allocation=50_000_000),
            AllocationRule(name="Portfolio B", target_id="p2", min_allocation=0, max_allocation=50_000_000),
            AllocationRule(name="Portfolio C", target_id="p3", min_allocation=0, max_allocation=50_000_000),
        ]

        request = AllocationRequest(
            pool_id=pool.pool_id,
            amount=90_000_000,
            method=AllocationMethod.EQUAL_WEIGHT,
            rules=rules,
        )
        result = allocator.allocate(request)

        assert result.total_allocated > 0
        assert len(result.allocations) == 3
        # Each should be ~30M
        for amount in result.allocations.values():
            assert 29_000_000 <= amount <= 31_000_000

    def test_risk_parity_allocation(self, allocator, pool):
        rules = [
            AllocationRule(name="Low Risk", target_id="low", conditions={"volatility": 0.10}),
            AllocationRule(name="Medium Risk", target_id="med", conditions={"volatility": 0.20}),
            AllocationRule(name="High Risk", target_id="high", conditions={"volatility": 0.40}),
        ]

        request = AllocationRequest(
            pool_id=pool.pool_id,
            amount=60_000_000,
            method=AllocationMethod.RISK_PARITY,
            rules=rules,
        )
        result = allocator.allocate(request)

        assert result.total_allocated > 0
        # Low risk should get the most allocation (inverse vol)
        assert result.allocations["low"] > result.allocations["high"]

    def test_kelly_allocation(self, allocator, pool):
        rules = [
            AllocationRule(
                name="High Win Rate",
                target_id="good",
                conditions={"win_rate": 0.70, "odds": 1.5},
            ),
            AllocationRule(
                name="Low Win Rate",
                target_id="bad",
                conditions={"win_rate": 0.40, "odds": 0.8},
            ),
        ]

        request = AllocationRequest(
            pool_id=pool.pool_id,
            amount=50_000_000,
            method=AllocationMethod.KELLY,
            rules=rules,
        )
        result = allocator.allocate(request)

        assert result.total_allocated > 0
        # "good" should get more capital
        assert result.allocations.get("good", 0) > result.allocations.get("bad", 0)

    def test_max_allocation_limit(self, allocator, pool):
        rules = [
            AllocationRule(name="Capped", target_id="cap", max_allocation=10_000_000),
            AllocationRule(name="Uncapped", target_id="free"),
        ]

        request = AllocationRequest(
            pool_id=pool.pool_id,
            amount=100_000_000,
            method=AllocationMethod.EQUAL_WEIGHT,
            rules=rules,
        )
        result = allocator.allocate(request)

        assert result.allocations.get("cap", 0) <= 10_000_000

    def test_capital_flow(self, allocator, pool):
        flow = CapitalFlow(
            flow_type="deposit",
            to_id=pool.pool_id,
            amount=10_000_000,
            reason="Additional capital",
        )
        allocator.record_flow(flow)

        updated_pool = allocator.get_pool(pool.pool_id)
        assert updated_pool.total_capital == 110_000_000

        flows = allocator.get_flows(flow_type="deposit")
        assert len(flows) == 1

    def test_min_allocation(self, allocator, pool):
        rules = [
            AllocationRule(name="Small", target_id="s", min_allocation=30_000_000, max_allocation=100_000_000),
            AllocationRule(name="Tiny", target_id="t", min_allocation=30_000_000, max_allocation=100_000_000),
        ]

        request = AllocationRequest(
            pool_id=pool.pool_id,
            amount=100_000_000,
            method=AllocationMethod.EQUAL_WEIGHT,
            rules=rules,
        )
        result = allocator.allocate(request)

        # Each should get at least min_allocation (but pool is 100M so 50M each still meets min)
        for target_id, amount in result.allocations.items():
            if amount > 0:
                assert amount >= 30_000_000

    def test_get_summary(self, allocator, pool):
        summary = allocator.get_summary()
        assert summary["total_pools"] == 1
        assert summary["total_capital"] == 100_000_000
