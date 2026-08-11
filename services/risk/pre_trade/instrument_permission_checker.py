"""
Instrument Permission Checker — Validates account trading permissions.

Ensures the account is authorized to trade the requested instrument
type and the specific symbol. Supports equities, ETFs, futures,
options, forex, crypto, and other asset classes.

Logic::

    Account → Instrument Type → Symbol Permission → PASS / FAIL
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .pre_trade_context import PreTradeContext
from .risk_request import OrderSide
from .risk_reason import RiskReason, ReasonCategory

logger = logging.getLogger(__name__)


class InstrumentPermissionChecker:
    """
    Validates that the account has permission to trade the requested instrument.

    Checks account-level permissions for:
    - Instrument type (equity, future, option, forex, crypto, etc.)
    - Specific symbols (restricted/permitted lists)
    - Order side (e.g., short selling permissions)
    - Exchange membership

    Usage::

        checker = InstrumentPermissionChecker(
            account_permissions={"ACC-001": ["equity", "etf", "option"]},
        )
        await checker.check(ctx)
    """

    def __init__(
        self,
        account_permissions: Optional[dict[str, list[str]]] = None,
        restricted_symbols: Optional[set[str]] = None,
        allowed_exchanges: Optional[set[str]] = None,
        allow_short_selling: bool = True,
    ) -> None:
        self._account_permissions = account_permissions or {}
        self._restricted_symbols = restricted_symbols or set()
        self._allowed_exchanges = allowed_exchanges or set()
        self._allow_short_selling = allow_short_selling

    async def check(self, ctx: PreTradeContext) -> None:
        """Check instrument trading permissions."""
        request = ctx.request
        account_state = ctx.account_state or request.metadata.get("account_state", {})

        # Get account permissions
        account_perms = self._account_permissions.get(
            request.account_id,
            account_state.get("permissions", []),
        )

        # Instrument type permission check
        inst_type = request.instrument_type.value
        if account_perms and inst_type not in account_perms:
            reason = RiskReason.blocking(
                category=ReasonCategory.INSTRUMENT_PERMISSION,
                message=(
                    f"Account {request.account_id} is not permitted to trade "
                    f"`{inst_type}` instruments."
                ),
                checker="InstrumentPermissionChecker",
                resolution="Contact your administrator to request trading permissions.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "InstrumentPermissionChecker", passed=False,
                metadata={"instrument_type": inst_type, "permissions": account_perms},
            )
            return

        # Restricted symbol check
        if request.symbol in self._restricted_symbols:
            reason = RiskReason.blocking(
                category=ReasonCategory.INSTRUMENT_PERMISSION,
                message=(
                    f"Symbol `{request.symbol}` is on the restricted list "
                    f"and cannot be traded."
                ),
                checker="InstrumentPermissionChecker",
                resolution="Contact compliance for approval to trade this symbol.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "InstrumentPermissionChecker", passed=False,
                metadata={"symbol": request.symbol, "restricted": True},
            )
            return

        # Short selling permission
        if request.side == OrderSide.SELL_SHORT and not self._allow_short_selling:
            reason = RiskReason.blocking(
                category=ReasonCategory.INSTRUMENT_PERMISSION,
                message=(
                    f"Short selling is not permitted for account "
                    f"{request.account_id}."
                ),
                checker="InstrumentPermissionChecker",
                resolution="Enable short selling permission or use a different order side.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "InstrumentPermissionChecker", passed=False,
                metadata={"side": "SELL_SHORT", "allowed": False},
            )
            return

        # Exchange permission check
        if self._allowed_exchanges and request.exchange:
            if request.exchange not in self._allowed_exchanges:
                reason = RiskReason.warning(
                    category=ReasonCategory.INSTRUMENT_PERMISSION,
                    message=(
                        f"Exchange `{request.exchange}` is not in the "
                        f"allowed exchange list."
                    ),
                    checker="InstrumentPermissionChecker",
                    resolution="Verify exchange connectivity and permissions.",
                )
                ctx.add_reason(reason)

        ctx.add_checker_result(
            "InstrumentPermissionChecker", passed=True,
            metadata={
                "instrument_type": inst_type,
                "symbol": request.symbol,
                "exchange": request.exchange,
            },
        )
