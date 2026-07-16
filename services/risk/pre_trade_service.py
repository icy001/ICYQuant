"""
Pre-trade risk service.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from .account import AccountRiskInfo
from .audit_service import RiskAuditService
from .context import RiskContext
from .engine import RiskEngine
from .mapper import RiskRequestMapper
from .providers import AccountProvider, PositionProvider
from .registry import default_rules
from .validators import ensure_approved


class PreTradeRiskService:
    def __init__(
        self,
        engine: Optional[RiskEngine] = None,
        position_provider: Optional[PositionProvider] = None,
        account_provider: Optional[AccountProvider] = None,
        audit_service: Optional[RiskAuditService] = None,
    ):
        self.engine = engine or RiskEngine(
            default_rules()
        )
        self.position_provider = position_provider
        self.account_provider = account_provider
        self.audit_service = audit_service

    async def evaluate(
        self,
        order,
    ):
        request = RiskRequestMapper.from_order(
            order
        )

        context = await self._build_context(request)

        result = self.engine.evaluate(
            request,
            context,
        )

        if self.audit_service:
            order_id = getattr(order, "id", None) or "UNKNOWN"
            await self.audit_service.record(
                order_id=order_id,
                account_id=order.account_id,
                result=result,
            )

        ensure_approved(result)

        return result

    async def _build_context(self, request) -> RiskContext:
        if self.position_provider:
            current_position = await self.position_provider.get_position(
                request.account_id,
                request.symbol,
            )
        else:
            current_position = Decimal("0")

        if self.account_provider:
            account = await self.account_provider.get_account_risk_info(
                request.account_id,
            )
        else:
            account = AccountRiskInfo(
                account_id=request.account_id,
                equity=Decimal("0"),
                used_margin=Decimal("0"),
            )

        return RiskContext(
            account_id=request.account_id,
            symbol=request.symbol,
            current_position=current_position,
            account=account,
        )