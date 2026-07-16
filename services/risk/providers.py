"""
Risk data providers.
"""

from __future__ import annotations

from decimal import Decimal

from .account import AccountRiskInfo


class PositionProvider:
    async def get_position(
        self,
        account_id: str,
        symbol: str,
    ) -> Decimal:
        """
        Return current net position.
        """
        raise NotImplementedError


class AccountProvider:
    async def get_account_risk_info(
        self,
        account_id: str,
    ) -> AccountRiskInfo:
        """
        Return account risk information.
        """
        raise NotImplementedError