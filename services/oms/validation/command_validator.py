"""CommandValidator — validates commands before processing."""
from __future__ import annotations

from services.oms.commands.order_command import OrderCommand
from services.oms.commands.create_order import CreateOrderCommand
from services.oms.commands.apply_execution import ApplyExecutionCommand
from services.oms.results.command_errors import CommandValidationError


class CommandValidator:
    """Validates commands before they reach the aggregate.

    Checks:
      - Required fields are present
      - Field values are valid
      - Command-specific constraints
    """

    @staticmethod
    def validate(command: OrderCommand) -> None:
        """Validate a command. Raises CommandValidationError on failure."""
        if not command.command_id:
            raise CommandValidationError(
                "", "MISSING_COMMAND_ID", "Command must have a command_id",
            )

        handler = _VALIDATORS.get(type(command))
        if handler:
            handler(command)

    @staticmethod
    def validate_create(cmd: CreateOrderCommand) -> None:
        if not cmd.symbol:
            raise CommandValidationError(
                cmd.command_id, "MISSING_SYMBOL", "Symbol is required",
            )
        if not cmd.side:
            raise CommandValidationError(
                cmd.command_id, "MISSING_SIDE", "Side is required",
            )
        if cmd.quantity <= 0:
            raise CommandValidationError(
                cmd.command_id, "INVALID_QUANTITY",
                f"Quantity must be positive, got {cmd.quantity}",
            )
        if not cmd.certificate_id:
            raise CommandValidationError(
                cmd.command_id, "MISSING_CERTIFICATE",
                "Certificate ID is required",
            )
        if not cmd.lineage_id:
            raise CommandValidationError(
                cmd.command_id, "MISSING_LINEAGE",
                "Lineage ID is required",
            )
        if cmd.order_type in ("LIMIT", "STOP_LIMIT") and cmd.price <= 0:
            raise CommandValidationError(
                cmd.command_id, "INVALID_PRICE",
                f"Limit order requires positive price, got {cmd.price}",
            )

    @staticmethod
    def validate_execution(cmd: ApplyExecutionCommand) -> None:
        if not cmd.execution_id:
            raise CommandValidationError(
                cmd.command_id, "MISSING_EXECUTION_ID",
                "Execution ID is required",
            )
        if cmd.fill_quantity <= 0:
            raise CommandValidationError(
                cmd.command_id, "INVALID_FILL_QUANTITY",
                f"Fill quantity must be positive, got {cmd.fill_quantity}",
            )
        if cmd.fill_price <= 0:
            raise CommandValidationError(
                cmd.command_id, "INVALID_FILL_PRICE",
                f"Fill price must be positive, got {cmd.fill_price}",
            )


_VALIDATORS = {
    CreateOrderCommand: CommandValidator.validate_create,
    ApplyExecutionCommand: CommandValidator.validate_execution,
}
