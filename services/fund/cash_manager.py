"""Cash Manager.

Real-time cash position management for the fund.

Tracks:
    - Total cash balance
    - Frozen cash (pending orders)
    - Pending redemption reserves
    - Fee reserves
    - Margin requirements
    - Investable cash

The Portfolio Engine uses investable cash to constrain
new position sizing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from services.fund.models import CashReserve, Fund


class CashManager:
    """Manages fund cash positions and reserves.

    Usage::

        manager = CashManager()
        manager.initialize(fund, total_cash=30_000_000)
        manager.freeze(5_000_000, reason="pending_buy_order")
        investable = manager.investable  # 25_000_000
        manager.unfreeze(5_000_000)
        manager.reserve_fees(20_548)
    """

    def __init__(self) -> None:
        self._reserves: Dict[str, CashReserve] = {}
        self._audit_log: Dict[str, List[Dict[str, object]]] = {}

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(self, fund: Fund, total_cash: Optional[float] = None) -> CashReserve:
        """Create or reset cash reserve for a fund."""
        if total_cash is None:
            total_cash = fund.cash_balance

        reserve = CashReserve(
            fund_id=fund.fund_id,
            total=total_cash,
        )
        self._reserves[fund.fund_id] = reserve
        self._log(fund.fund_id, "INIT", {"total_cash": total_cash})
        return reserve

    def get(self, fund_id: str) -> CashReserve:
        """Get cash reserve for a fund (auto-initialize if missing)."""
        if fund_id not in self._reserves:
            self._reserves[fund_id] = CashReserve(fund_id=fund_id)
        return self._reserves[fund_id]

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def deposit(self, fund_id: str, amount: float, reason: str = "deposit") -> CashReserve:
        """Add cash to the fund."""
        reserve = self.get(fund_id)
        reserve.total += amount
        self._log(fund_id, "DEPOSIT", {"amount": amount, "reason": reason})
        return reserve

    def withdraw(self, fund_id: str, amount: float, reason: str = "withdrawal") -> CashReserve:
        """Remove cash from the fund."""
        reserve = self.get(fund_id)
        if amount > reserve.available:
            raise ValueError(
                f"Insufficient available cash for withdrawal: {reserve.available} < {amount}"
            )
        reserve.total -= amount
        self._log(fund_id, "WITHDRAW", {"amount": amount, "reason": reason})
        return reserve

    def freeze(self, fund_id: str, amount: float, reason: str = "order") -> CashReserve:
        """Freeze cash for a pending operation."""
        reserve = self.get(fund_id)
        reserve.freeze(amount)
        self._log(fund_id, "FREEZE", {"amount": amount, "reason": reason})
        return reserve

    def unfreeze(self, fund_id: str, amount: float, reason: str = "order_complete") -> CashReserve:
        """Release previously frozen cash."""
        reserve = self.get(fund_id)
        reserve.unfreeze(amount)
        self._log(fund_id, "UNFREEZE", {"amount": amount, "reason": reason})
        return reserve

    def reserve_redemption(self, fund_id: str, amount: float) -> CashReserve:
        """Reserve cash for pending redemption payment."""
        reserve = self.get(fund_id)
        reserve.reserve_redemption(amount)
        self._log(fund_id, "RESERVE_REDEMPTION", {"amount": amount})
        return reserve

    def pay_redemption(self, fund_id: str, amount: float) -> CashReserve:
        """Pay out a settled redemption."""
        reserve = self.get(fund_id)
        reserve.release_redemption(amount)
        self._log(fund_id, "PAY_REDEMPTION", {"amount": amount})
        return reserve

    def reserve_fees(self, fund_id: str, amount: float) -> CashReserve:
        """Reserve cash for fee payments."""
        reserve = self.get(fund_id)
        if amount > reserve.available:
            raise ValueError(f"Insufficient cash for fee reserve: {reserve.available} < {amount}")
        reserve.fee_reserve += amount
        self._log(fund_id, "RESERVE_FEES", {"amount": amount})
        return reserve

    def pay_fees(self, fund_id: str, amount: float) -> CashReserve:
        """Pay out reserved fees."""
        reserve = self.get(fund_id)
        reserve.total -= amount
        reserve.fee_reserve = max(0.0, reserve.fee_reserve - amount)
        self._log(fund_id, "PAY_FEES", {"amount": amount})
        return reserve

    def set_margin(self, fund_id: str, amount: float) -> CashReserve:
        """Set margin requirement."""
        reserve = self.get(fund_id)
        reserve.margin = amount
        self._log(fund_id, "SET_MARGIN", {"amount": amount})
        return reserve

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def investable(self, fund_id: Optional[str] = None) -> float:
        """Get investable cash for a fund."""
        if fund_id is None:
            # Sum across all funds
            return sum(r.available for r in self._reserves.values())
        return self.get(fund_id).available

    def investable_for(self, fund_id: str) -> float:
        return self.get(fund_id).available

    def total_cash(self, fund_id: str) -> float:
        return self.get(fund_id).total

    def frozen_cash(self, fund_id: str) -> float:
        return self.get(fund_id).frozen

    def summary(self, fund_id: str) -> Dict[str, object]:
        """Cash position summary."""
        return self.get(fund_id).to_dict()

    def can_allocate(self, fund_id: str, amount: float) -> Tuple[bool, str]:
        """Check if fund can allocate the given amount."""
        reserve = self.get(fund_id)
        if amount <= 0:
            return False, "Amount must be positive"
        if amount > reserve.available:
            return False, f"Insufficient investable cash: {reserve.available:.2f} < {amount:.2f}"
        return True, "OK"

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def _log(self, fund_id: str, operation: str, details: Dict[str, object]) -> None:
        if fund_id not in self._audit_log:
            self._audit_log[fund_id] = []
        self._audit_log[fund_id].append({
            "timestamp": datetime.utcnow().isoformat(),
            "operation": operation,
            **details,
        })

    def audit_trail(self, fund_id: str) -> List[Dict[str, object]]:
        """Get the full audit log for a fund's cash operations."""
        return self._audit_log.get(fund_id, [])
