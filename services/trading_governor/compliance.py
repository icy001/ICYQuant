"""Compliance Authority – validates trading against session, symbol, holiday, and regulatory rules."""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class ComplianceStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass
class ComplianceResult:
    status: ComplianceStatus
    rule_name: str
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


class ComplianceAuthority:
    """Validates trading permissions against compliance and regulatory constraints.

    Checks: trading session, restricted symbols, market holidays, compliance rules.
    """

    def __init__(self) -> None:
        self._restricted_symbols: Set[str] = set()
        self._market_holidays: Set[date] = set()
        self._trading_session_start: Optional[time] = None
        self._trading_session_end: Optional[time] = None
        self._compliance_rules: Dict[str, str] = {}

    def validate(self, allowed: bool) -> bool:
        """Basic compliance check.

        Args:
            allowed: whether trading is allowed by compliance.

        Returns:
            True if allowed.
        """
        return allowed

    def add_restricted_symbol(self, symbol: str) -> None:
        self._restricted_symbols.add(symbol.upper())

    def add_market_holiday(self, holiday: date) -> None:
        self._market_holidays.add(holiday)

    def set_trading_session(self, start: time, end: time) -> None:
        self._trading_session_start = start
        self._trading_session_end = end

    def add_rule(self, name: str, description: str) -> None:
        self._compliance_rules[name] = description

    def check_symbol(self, symbol: str) -> ComplianceResult:
        """Check if a symbol is restricted."""
        ok = symbol.upper() not in self._restricted_symbols
        return ComplianceResult(
            status=ComplianceStatus.PASS if ok else ComplianceStatus.FAIL,
            rule_name="restricted_symbol",
            message=f"Symbol '{symbol}' is {'allowed' if ok else 'restricted'}",
            details={"symbol": symbol, "restricted": not ok},
        )

    def check_session(self, check_time: Optional[datetime] = None) -> ComplianceResult:
        """Check if current time is within trading session."""
        if self._trading_session_start is None or self._trading_session_end is None:
            return ComplianceResult(
                status=ComplianceStatus.PASS,
                rule_name="trading_session",
                message="No session configured — always allowed",
            )

        t = (check_time or datetime.now(timezone.utc)).time()
        ok = self._trading_session_start <= t <= self._trading_session_end
        return ComplianceResult(
            status=ComplianceStatus.PASS if ok else ComplianceStatus.FAIL,
            rule_name="trading_session",
            message=f"Trading session: {self._trading_session_start}-{self._trading_session_end}",
            details={"current_time": str(t), "in_session": ok},
        )

    def check_holiday(self, check_date: Optional[date] = None) -> ComplianceResult:
        """Check if today is a market holiday."""
        d = check_date or date.today()
        ok = d not in self._market_holidays
        return ComplianceResult(
            status=ComplianceStatus.PASS if ok else ComplianceStatus.FAIL,
            rule_name="market_holiday",
            message=f"{d} is {'a trading day' if ok else 'a holiday'}",
            details={"date": str(d), "holiday": not ok},
        )

    def validate_all(
        self,
        symbol: str,
        check_time: Optional[datetime] = None,
        check_date: Optional[date] = None,
    ) -> List[ComplianceResult]:
        """Run all compliance checks.

        Returns:
            List of ComplianceResult for each check.
        """
        return [
            self.check_symbol(symbol),
            self.check_session(check_time),
            self.check_holiday(check_date),
        ]

    def is_approved(
        self,
        symbol: str,
        check_time: Optional[datetime] = None,
        check_date: Optional[date] = None,
    ) -> bool:
        """Return True if all compliance checks pass."""
        results = self.validate_all(symbol, check_time, check_date)
        return all(r.status == ComplianceStatus.PASS for r in results)

    @property
    def restricted_count(self) -> int:
        return len(self._restricted_symbols)

    @property
    def holiday_count(self) -> int:
        return len(self._market_holidays)
