"""Tests for command validation."""

import unittest

from services.oms.commands.create_order import CreateOrderCommand
from services.oms.commands.apply_execution import ApplyExecutionCommand
from services.oms.commands.command_metadata import CommandMetadata
from services.oms.validation.command_validator import CommandValidator
from services.oms.results.command_errors import CommandValidationError


class TestCommandValidation(unittest.TestCase):

    def test_valid_create_command(self):
        cmd = CreateOrderCommand(
            metadata=CommandMetadata(command_id="CMD-1"),
            symbol="NVDA", side="BUY", order_type="MARKET",
            quantity=1000, certificate_id="C-1", lineage_id="L-1",
        )
        CommandValidator.validate(cmd)

    def test_missing_symbol(self):
        cmd = CreateOrderCommand(
            metadata=CommandMetadata(command_id="CMD-1"),
            side="BUY", quantity=1000,
            certificate_id="C-1", lineage_id="L-1",
        )
        with self.assertRaises(CommandValidationError):
            CommandValidator.validate(cmd)

    def test_missing_certificate(self):
        cmd = CreateOrderCommand(
            metadata=CommandMetadata(command_id="CMD-1"),
            symbol="NVDA", side="BUY", quantity=1000,
            lineage_id="L-1",
        )
        with self.assertRaises(CommandValidationError):
            CommandValidator.validate(cmd)

    def test_invalid_quantity(self):
        cmd = CreateOrderCommand(
            metadata=CommandMetadata(command_id="CMD-1"),
            symbol="NVDA", side="BUY", quantity=-100,
            certificate_id="C-1", lineage_id="L-1",
        )
        with self.assertRaises(CommandValidationError):
            CommandValidator.validate(cmd)

    def test_limit_order_requires_price(self):
        cmd = CreateOrderCommand(
            metadata=CommandMetadata(command_id="CMD-1"),
            symbol="NVDA", side="BUY", order_type="LIMIT",
            quantity=1000, price=0,
            certificate_id="C-1", lineage_id="L-1",
        )
        with self.assertRaises(CommandValidationError):
            CommandValidator.validate(cmd)

    def test_valid_execution_command(self):
        cmd = ApplyExecutionCommand(
            metadata=CommandMetadata(command_id="CMD-1"),
            order_id="ORD-1",
            execution_id="EXEC-1", fill_quantity=300, fill_price=180,
        )
        CommandValidator.validate(cmd)

    def test_execution_missing_id(self):
        cmd = ApplyExecutionCommand(
            metadata=CommandMetadata(command_id="CMD-1"),
            order_id="ORD-1",
            fill_quantity=300, fill_price=180,
        )
        with self.assertRaises(CommandValidationError):
            CommandValidator.validate(cmd)


if __name__ == '__main__':
    unittest.main()
