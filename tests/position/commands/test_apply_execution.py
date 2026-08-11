"""
Tests for ApplyExecutionCommand — validation and fill delta logic.
"""

from __future__ import annotations

import pytest

from services.position.commands.apply_execution import ApplyExecutionCommand
from services.position.exceptions.position_error import (
    InvalidExecutionError,
    OverFillError,
)


class TestCommandValidation:
    """Command validation rules."""

    def test_valid_command_passes(self) -> None:
        cmd = ApplyExecutionCommand(
            account_id="ACC-001",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=500,
            fill_price=180.0,
            order_id="ORD-001",
            execution_id="EXEC-001",
        )
        cmd.validate()  # should not raise

    def test_missing_account_id(self) -> None:
        cmd = ApplyExecutionCommand(
            account_id="",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=500,
            fill_price=180.0,
            order_id="ORD-001",
            execution_id="EXEC-001",
        )
        with pytest.raises(InvalidExecutionError, match="account_id"):
            cmd.validate()

    def test_missing_instrument_id(self) -> None:
        cmd = ApplyExecutionCommand(
            account_id="ACC-001",
            instrument_id="",
            side="BUY",
            fill_quantity=500,
            fill_price=180.0,
            order_id="ORD-001",
            execution_id="EXEC-001",
        )
        with pytest.raises(InvalidExecutionError, match="instrument_id"):
            cmd.validate()

    def test_missing_order_id(self) -> None:
        cmd = ApplyExecutionCommand(
            account_id="ACC-001",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=500,
            fill_price=180.0,
            order_id="",
            execution_id="EXEC-001",
        )
        with pytest.raises(InvalidExecutionError, match="order_id"):
            cmd.validate()

    def test_missing_execution_id(self) -> None:
        cmd = ApplyExecutionCommand(
            account_id="ACC-001",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=500,
            fill_price=180.0,
            order_id="ORD-001",
            execution_id="",
        )
        with pytest.raises(InvalidExecutionError, match="execution_id"):
            cmd.validate()

    def test_zero_quantity(self) -> None:
        cmd = ApplyExecutionCommand(
            account_id="ACC-001",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=0,
            fill_price=180.0,
            order_id="ORD-001",
            execution_id="EXEC-001",
        )
        with pytest.raises(InvalidExecutionError, match="fill_quantity"):
            cmd.validate()

    def test_negative_quantity(self) -> None:
        cmd = ApplyExecutionCommand(
            account_id="ACC-001",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=-100,
            fill_price=180.0,
            order_id="ORD-001",
            execution_id="EXEC-001",
        )
        with pytest.raises(InvalidExecutionError, match="fill_quantity"):
            cmd.validate()

    def test_zero_price(self) -> None:
        cmd = ApplyExecutionCommand(
            account_id="ACC-001",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=100,
            fill_price=0,
            order_id="ORD-001",
            execution_id="EXEC-001",
        )
        with pytest.raises(InvalidExecutionError, match="fill_price"):
            cmd.validate()

    def test_invalid_side(self) -> None:
        cmd = ApplyExecutionCommand(
            account_id="ACC-001",
            instrument_id="NVDA",
            side="HOLD",
            fill_quantity=100,
            fill_price=180.0,
            order_id="ORD-001",
            execution_id="EXEC-001",
        )
        with pytest.raises(InvalidExecutionError, match="side"):
            cmd.validate()


class TestFillDelta:
    """Fill delta computation."""

    def test_first_fill_delta_equal_to_cumulative(self) -> None:
        cmd = ApplyExecutionCommand(
            account_id="ACC-001",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=500,
            fill_price=180.0,
            order_id="ORD-001",
            execution_id="EXEC-001",
            cumulative_fill=500,
            previous_cumulative_fill=0,
        )
        assert cmd.delta == 500
        assert cmd.is_effective is True

    def test_partial_fill_delta(self) -> None:
        cmd = ApplyExecutionCommand(
            account_id="ACC-001",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=1000,
            fill_price=180.0,
            order_id="ORD-001",
            execution_id="EXEC-002",
            cumulative_fill=1000,
            previous_cumulative_fill=300,
        )
        assert cmd.delta == 700

    def test_full_fill_delta_after_partial(self) -> None:
        cmd = ApplyExecutionCommand(
            account_id="ACC-001",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=1000,
            fill_price=180.50,
            order_id="ORD-001",
            execution_id="EXEC-003",
            cumulative_fill=1000,
            previous_cumulative_fill=700,
        )
        assert cmd.delta == 300

    def test_zero_delta_when_no_progress(self) -> None:
        cmd = ApplyExecutionCommand(
            account_id="ACC-001",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=500,
            fill_price=180.0,
            order_id="ORD-001",
            execution_id="EXEC-001",
            cumulative_fill=500,
            previous_cumulative_fill=500,
        )
        assert cmd.delta == 0
        assert cmd.is_effective is False

    def test_negative_delta_detected(self) -> None:
        cmd = ApplyExecutionCommand(
            account_id="ACC-001",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=500,
            fill_price=180.0,
            order_id="ORD-001",
            execution_id="EXEC-001",
            cumulative_fill=300,
            previous_cumulative_fill=500,
        )
        assert cmd.delta == -200
        assert cmd.has_negative_delta is True


class TestOverFillDetection:
    """Over-fill protection."""

    def test_ensure_valid_delta_raises_on_negative(self) -> None:
        cmd = ApplyExecutionCommand(
            account_id="ACC-001",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=500,
            fill_price=180.0,
            order_id="ORD-001",
            execution_id="EXEC-001",
            ordered_quantity=1000,
            cumulative_fill=300,
            previous_cumulative_fill=500,
        )
        with pytest.raises(InvalidExecutionError, match="Negative fill delta"):
            cmd.ensure_valid_delta()

    def test_ensure_valid_delta_raises_on_over_fill(self) -> None:
        cmd = ApplyExecutionCommand(
            account_id="ACC-001",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=0,  # not used for overfill check
            fill_price=180.0,
            order_id="ORD-001",
            execution_id="EXEC-001",
            ordered_quantity=1000,
            cumulative_fill=1200,
            previous_cumulative_fill=800,
        )
        with pytest.raises(OverFillError):
            cmd.ensure_valid_delta()

    def test_ensure_valid_delta_passes_when_valid(self) -> None:
        cmd = ApplyExecutionCommand(
            account_id="ACC-001",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=1000,
            fill_price=180.0,
            order_id="ORD-001",
            execution_id="EXEC-001",
            ordered_quantity=1000,
            cumulative_fill=1000,
            previous_cumulative_fill=500,
        )
        cmd.ensure_valid_delta()  # no-op for valid


class TestCommandHelpers:
    """Convenience properties."""

    def test_is_buy(self) -> None:
        cmd = ApplyExecutionCommand("ACC", "NVDA", "BUY", 100, 180, "O1", "E1")
        assert cmd.is_buy is True
        assert cmd.is_sell is False

    def test_is_sell(self) -> None:
        cmd = ApplyExecutionCommand("ACC", "NVDA", "SELL", 100, 180, "O1", "E1")
        assert cmd.is_sell is True
        assert cmd.is_buy is False

    def test_position_side_mapping(self) -> None:
        buy_cmd = ApplyExecutionCommand("ACC", "NVDA", "BUY", 100, 180, "O1", "E1")
        sell_cmd = ApplyExecutionCommand("ACC", "NVDA", "SELL", 100, 180, "O1", "E1")
        assert buy_cmd.position_side == "LONG"
        assert sell_cmd.position_side == "SHORT"

    def test_signed_quantity_buy_positive(self) -> None:
        cmd = ApplyExecutionCommand("ACC", "NVDA", "BUY", 100, 180, "O1", "E1",
                                    cumulative_fill=100, previous_cumulative_fill=0)
        assert cmd.signed_quantity == 100

    def test_signed_quantity_sell_negative(self) -> None:
        cmd = ApplyExecutionCommand("ACC", "NVDA", "SELL", 100, 180, "O1", "E1",
                                    cumulative_fill=100, previous_cumulative_fill=0)
        assert cmd.signed_quantity == -100

    def test_to_dict(self) -> None:
        cmd = ApplyExecutionCommand(
            account_id="ACC-001",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=500,
            fill_price=180.0,
            order_id="ORD-001",
            execution_id="EXEC-001",
            correlation_id="CORR-001",
        )
        d = cmd.to_dict()
        assert d["account_id"] == "ACC-001"
        assert d["correlation_id"] == "CORR-001"
        assert "delta" in d
