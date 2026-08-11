from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class RecoveryScopeType(str, Enum):
    """Granularity of the recovery operation.

    Priority (smallest safe scope first):
        EXECUTION → ORDER → INSTRUMENT → ACCOUNT → PORTFOLIO
    """

    EXECUTION = "EXECUTION"
    ORDER = "ORDER"
    ACCOUNT = "ACCOUNT"
    INSTRUMENT = "INSTRUMENT"
    PORTFOLIO = "PORTFOLIO"


@dataclass
class RecoveryScope:
    """Defines the target scope for a recovery operation.

    Example:
        RecoveryScope(
            scope_type=RecoveryScopeType.EXECUTION,
            execution_id="EXEC-001",
            account_id="ACC-001",
            instrument_id="NVDA",
        )
    """

    scope_type: RecoveryScopeType
    account_id: Optional[str] = None
    instrument_id: Optional[str] = None
    execution_id: Optional[str] = None
    order_id: Optional[str] = None

    @property
    def recovery_key(self) -> str:
        """Unique key for deduplication and locking.

        Format: {scope_type}:{account_id}:{instrument_id}:{execution_id or order_id}
        """
        parts = [self.scope_type.value]
        if self.account_id:
            parts.append(self.account_id)
        if self.instrument_id:
            parts.append(self.instrument_id)
        if self.execution_id:
            parts.append(self.execution_id)
        elif self.order_id:
            parts.append(self.order_id)
        return ":".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scope_type": self.scope_type.value,
            "account_id": self.account_id,
            "instrument_id": self.instrument_id,
            "execution_id": self.execution_id,
            "order_id": self.order_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryScope":
        return cls(
            scope_type=RecoveryScopeType(data["scope_type"]),
            account_id=data.get("account_id"),
            instrument_id=data.get("instrument_id"),
            execution_id=data.get("execution_id"),
            order_id=data.get("order_id"),
        )

    @classmethod
    def for_execution(
        cls,
        execution_id: str,
        account_id: str,
        instrument_id: str,
    ) -> "RecoveryScope":
        return cls(
            scope_type=RecoveryScopeType.EXECUTION,
            execution_id=execution_id,
            account_id=account_id,
            instrument_id=instrument_id,
        )

    @classmethod
    def for_order(
        cls,
        order_id: str,
        account_id: str,
        instrument_id: str,
    ) -> "RecoveryScope":
        return cls(
            scope_type=RecoveryScopeType.ORDER,
            order_id=order_id,
            account_id=account_id,
            instrument_id=instrument_id,
        )

    @classmethod
    def for_account(cls, account_id: str) -> "RecoveryScope":
        return cls(
            scope_type=RecoveryScopeType.ACCOUNT,
            account_id=account_id,
        )

    @classmethod
    def for_instrument(
        cls,
        account_id: str,
        instrument_id: str,
    ) -> "RecoveryScope":
        return cls(
            scope_type=RecoveryScopeType.INSTRUMENT,
            account_id=account_id,
            instrument_id=instrument_id,
        )
