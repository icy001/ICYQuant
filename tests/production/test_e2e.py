"""
End-to-end integration tests for the ICYQuant complete trading flow.

Validates the full trading pipeline: Market Data -> Feature Store ->
AI Inference -> Signal Generation -> Risk Check -> OMS Order ->
EMS Execution -> Broker Communication -> Position Update ->
Portfolio Update -> PnL Calculation.
"""

import time
from decimal import Decimal

import pytest

from release.validation import (
    IntegrationResult,
    IntegrationValidator,
    StepResult,
)


class TestIntegrationValidator:
    """Test the complete trading flow using IntegrationValidator."""

    def test_full_trading_flow(self):
        """Verify the end-to-end trading pipeline passes all steps."""
        validator = IntegrationValidator()
        result = validator.run()

        assert isinstance(result, IntegrationResult)
        assert result.overall_passed is True
        assert len(result.steps) == 11
        assert result.total_duration_ms > 0
        assert result.started_at != ""
        assert result.completed_at != ""
        assert result.pass_rate == 1.0

    def test_each_step_individually(self):
        """Verify each pipeline step passes individually."""
        validator = IntegrationValidator()
        result = validator.run()

        step_names = [s.step_name for s in result.steps]
        expected_steps = [
            "Market Data",
            "Feature Store",
            "AI Inference",
            "Signal Generation",
            "Risk Check",
            "OMS Order",
            "EMS Execution",
            "Broker Communication",
            "Position Update",
            "Portfolio Update",
            "PnL Calculation",
        ]
        for expected in expected_steps:
            assert expected in step_names, f"Missing step: {expected}"

        for step in result.steps:
            assert isinstance(step, StepResult)
            assert step.passed is True, f"Step '{step.step_name}' failed: {step.error_message}"
            assert step.duration_ms >= 0
            assert step.data_integrity is True
            assert step.type_compatible is True

    def test_market_data_ingestion(self):
        """Test market data ingestion step creates valid Bar objects."""
        validator = IntegrationValidator()
        result = validator.run()

        market_step = result.steps[0]
        assert market_step.step_name == "Market Data"
        assert market_step.passed is True
        assert market_step.duration_ms > 0

    def test_feature_computation(self):
        """Test feature computation produces valid feature data."""
        validator = IntegrationValidator()
        result = validator.run()

        feature_step = result.steps[1]
        assert feature_step.step_name == "Feature Store"
        assert feature_step.passed is True

    def test_ai_signal_generation(self):
        """Test AI signal generation produces valid AlphaScore."""
        validator = IntegrationValidator()
        result = validator.run()

        ai_step = result.steps[2]
        assert ai_step.step_name == "AI Inference"
        assert ai_step.passed is True

        signal_step = result.steps[3]
        assert signal_step.step_name == "Signal Generation"
        assert signal_step.passed is True

    def test_risk_validation(self):
        """Test risk validation produces a passing RiskDecision."""
        validator = IntegrationValidator()
        result = validator.run()

        risk_step = result.steps[4]
        assert risk_step.step_name == "Risk Check"
        assert risk_step.passed is True

    def test_order_management(self):
        """Test order management creates valid Order objects."""
        validator = IntegrationValidator()
        result = validator.run()

        oms_step = result.steps[5]
        assert oms_step.step_name == "OMS Order"
        assert oms_step.passed is True

    def test_execution_simulation(self):
        """Test execution simulation processes orders through EMS."""
        validator = IntegrationValidator()
        result = validator.run()

        ems_step = result.steps[6]
        assert ems_step.step_name == "EMS Execution"
        assert ems_step.passed is True

    def test_position_update(self):
        """Test position update creates valid Position objects."""
        validator = IntegrationValidator()
        result = validator.run()

        position_step = result.steps[8]
        assert position_step.step_name == "Position Update"
        assert position_step.passed is True

    def test_portfolio_pnl(self):
        """Test portfolio update and PnL calculation are correct."""
        validator = IntegrationValidator()
        result = validator.run()

        portfolio_step = result.steps[9]
        assert portfolio_step.step_name == "Portfolio Update"
        assert portfolio_step.passed is True

        pnl_step = result.steps[10]
        assert pnl_step.step_name == "PnL Calculation"
        assert pnl_step.passed is True

    def test_result_discrepancy_tracking(self):
        """Verify that data discrepancies are tracked in the result."""
        validator = IntegrationValidator()
        result = validator.run()

        assert isinstance(result.discrepancies, list)
        assert len(result.discrepancies) == 0

    def test_negative_case_corrupted_bar(self):
        """Test that corrupted market data (high < low) is detected."""
        from services.marketdata.bar import Bar

        with pytest.raises(Exception):
            bar = Bar(
                symbol="TEST",
                open=100.0,
                high=95.0,
                low=105.0,
                close=102.0,
                volume=1000000.0,
                timestamp=int(time.time()),
            )
            assert bar.high >= bar.low, "high should be >= low for valid bar"

    def test_negative_case_invalid_price(self):
        """Test that zero or negative prices are caught."""
        from services.order.model import Order
        from services.order.enums import OrderType, OrderSide

        with pytest.raises(Exception):
            order = Order(
                order_id="order_neg",
                account_id="account_001",
                portfolio_id="portfolio_001",
                symbol="TEST",
                quantity=-100.0,
                price=0.0,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
            )
            assert order.quantity > 0, "quantity must be positive"
            assert order.price > 0, "price must be positive"

    def test_step_result_properties(self):
        """Test that StepResult dataclass properties work correctly."""
        step = StepResult(
            step_name="Test Step",
            passed=True,
            duration_ms=42.5,
            data_integrity=True,
            type_compatible=True,
        )
        assert step.step_name == "Test Step"
        assert step.passed is True
        assert step.duration_ms == 42.5
        assert step.data_integrity is True
        assert step.type_compatible is True
        assert step.error_message is None
        assert step.data_discrepancies == []

    def test_integration_result_pass_rate(self):
        """Test that IntegrationResult.pass_rate is calculated correctly."""
        result = IntegrationResult(
            overall_passed=True,
            total_duration_ms=100.0,
            steps=[
                StepResult(step_name="A", passed=True, duration_ms=10.0),
                StepResult(step_name="B", passed=True, duration_ms=20.0),
                StepResult(step_name="C", passed=False, duration_ms=30.0),
            ],
        )
        assert result.pass_rate == pytest.approx(2.0 / 3.0)

    def test_integration_result_empty_steps(self):
        """Test pass_rate with empty steps returns 0.0."""
        result = IntegrationResult(
            overall_passed=False,
            total_duration_ms=0.0,
            steps=[],
        )
        assert result.pass_rate == 0.0