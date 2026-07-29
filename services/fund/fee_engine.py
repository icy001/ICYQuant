"""Fee Engine.

Handles fund fee calculation and accrual:

    - Management Fee (annual %, accrued daily)
    - Performance Fee (above HWM / hurdle rate)
    - Administration Fee
    - Custody Fee
    - Subscription Fee
    - Redemption Fee

Supports:
    - High Water Mark (HWM)
    - Hurdle Rate
    - Crystallization Date (daily / monthly / quarterly / annually / on-redemption)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from services.fund.models import (
    CrystallizationMode,
    FeeSchedule,
    FeeType,
    Fund,
)


@dataclass
class FeeAccrual:
    """A single fee accrual record."""

    fund_id: str
    fee_type: FeeType
    amount: float
    date: date
    aum: float
    nav: float
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, object]:
        return {
            "fund_id": self.fund_id,
            "fee_type": self.fee_type.value,
            "amount": self.amount,
            "date": self.date.isoformat(),
            "aum": self.aum,
            "nav": self.nav,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class FeeReport:
    """Aggregated fee report for a period."""

    fund_id: str
    period_start: date
    period_end: date
    total_management_fee: float = 0.0
    total_performance_fee: float = 0.0
    total_administration_fee: float = 0.0
    total_custody_fee: float = 0.0
    total_subscription_fee: float = 0.0
    total_redemption_fee: float = 0.0

    @property
    def total_fees(self) -> float:
        return (
            self.total_management_fee
            + self.total_performance_fee
            + self.total_administration_fee
            + self.total_custody_fee
            + self.total_subscription_fee
            + self.total_redemption_fee
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "fund_id": self.fund_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_management_fee": self.total_management_fee,
            "total_performance_fee": self.total_performance_fee,
            "total_administration_fee": self.total_administration_fee,
            "total_custody_fee": self.total_custody_fee,
            "total_subscription_fee": self.total_subscription_fee,
            "total_redemption_fee": self.total_redemption_fee,
            "total_fees": self.total_fees,
        }


class FeeEngine:
    """Calculates and accrues fund fees.

    Usage::

        engine = FeeEngine()
        schedule = FeeSchedule(management_fee_pct=1.5, performance_fee_pct=20.0)

        # Daily management fee
        mgmt = engine.accrue_management_fee(fund, schedule)
        print(f"Daily mgmt fee: ${mgmt:.2f}")

        # Performance fee (quarterly crystallisation)
        perf = engine.calculate_performance_fee(fund, schedule)
        print(f"Performance fee: ${perf:.2f}")

        # Fee report
        report = engine.generate_report(fund.fund_id, start_date, end_date)
    """

    def __init__(self) -> None:
        self._accruals: Dict[str, List[FeeAccrual]] = {}

    # ------------------------------------------------------------------
    # Management Fee
    # ------------------------------------------------------------------

    def accrue_management_fee(
        self,
        fund: Fund,
        schedule: Optional[FeeSchedule] = None,
    ) -> FeeAccrual:
        """Accrue one day of management fee.

        daily_fee = AUM * annual_rate / 365

        If a FeeSchedule is provided, management_fee_pct is a percentage (e.g. 1.5 = 1.5%).
        If using the Fund directly, management_fee_rate is a decimal (e.g. 0.015 = 1.5%).
        """
        if schedule:
            rate = schedule.management_fee_pct / 100.0
        else:
            rate = fund.management_fee_rate
        aum = fund.aum
        daily_fee = aum * rate / 365.0

        accrual = FeeAccrual(
            fund_id=fund.fund_id,
            fee_type=FeeType.MANAGEMENT,
            amount=round(daily_fee, 2),
            date=fund.nav_date,
            aum=aum,
            nav=fund.nav,
        )
        self._record(fund.fund_id, accrual)
        return accrual

    def management_fee_for_period(
        self, fund: Fund, days: int, schedule: Optional[FeeSchedule] = None
    ) -> float:
        """Management fee for N days."""
        if schedule:
            rate = schedule.management_fee_pct / 100.0
        else:
            rate = fund.management_fee_rate
        return fund.aum * rate * days / 365.0

    # ------------------------------------------------------------------
    # Performance Fee
    # ------------------------------------------------------------------

    def calculate_performance_fee(
        self,
        fund: Fund,
        schedule: Optional[FeeSchedule] = None,
    ) -> float:
        """Calculate performance fee above HWM + hurdle.

        Formula:
            fee = max(0, (NAV - max(HWM, HWM * (1 + hurdle))) * shares * perf_fee_rate)
        """
        if schedule:
            perf_rate = schedule.performance_fee_pct / 100.0
        else:
            perf_rate = fund.performance_fee_rate
        hwm = schedule.high_water_mark if schedule else fund.high_water_mark
        hurdle = schedule.hurdle_rate if schedule else fund.hurdle_rate

        # Effective HWM after hurdle
        effective_hwm = hwm
        if hurdle > 0:
            effective_hwm = max(hwm, hwm * (1.0 + hurdle))

        excess_per_share = fund.nav - effective_hwm
        if excess_per_share <= 0:
            return 0.0

        total_shares = fund.total_shares if fund.total_shares > 0 else 1.0
        fee = excess_per_share * total_shares * perf_rate

        return round(fee, 2)

    def should_crystallize(
        self,
        fund: Fund,
        schedule: Optional[FeeSchedule] = None,
        as_of: Optional[date] = None,
    ) -> Tuple[bool, float]:
        """Determine if performance fee should crystallize today.

        Returns
        -------
        (should_crystallize, fee_amount)
        """
        mode = schedule.crystallization if schedule else fund.crystallization
        today = as_of or date.today()

        should = False
        if mode == CrystallizationMode.DAILY:
            should = True
        elif mode == CrystallizationMode.MONTHLY:
            should = today.day == 1 or today == today.replace(day=28)  # last day
        elif mode == CrystallizationMode.QUARTERLY:
            should = today.day == 1 and today.month in (1, 4, 7, 10)
        elif mode == CrystallizationMode.ANNUALLY:
            should = today.day == 1 and today.month == 1
        elif mode == CrystallizationMode.ON_REDEMPTION:
            should = False  # handled by redemption flow

        fee = self.calculate_performance_fee(fund, schedule) if should else 0.0

        # Record if crystallizing
        if should and fee > 0:
            accrual = FeeAccrual(
                fund_id=fund.fund_id,
                fee_type=FeeType.PERFORMANCE,
                amount=fee,
                date=today,
                aum=fund.aum,
                nav=fund.nav,
            )
            self._record(fund.fund_id, accrual)

        return should, fee

    # ------------------------------------------------------------------
    # Subscription / Redemption Fees
    # ------------------------------------------------------------------

    def subscription_fee(self, amount: float, schedule: Optional[FeeSchedule] = None) -> float:
        """Calculate subscription fee."""
        if schedule is None or schedule.subscription_fee_pct == 0:
            return 0.0
        return schedule.subscription_fee(amount)

    def redemption_fee(self, amount: float, schedule: Optional[FeeSchedule] = None) -> float:
        """Calculate redemption fee."""
        if schedule is None or schedule.redemption_fee_pct == 0:
            return 0.0
        return schedule.redemption_fee(amount)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def generate_report(
        self,
        fund_id: str,
        period_start: date,
        period_end: date,
    ) -> FeeReport:
        """Aggregate fees for a date range."""
        accruals = self._accruals.get(fund_id, [])
        report = FeeReport(fund_id=fund_id, period_start=period_start, period_end=period_end)

        for a in accruals:
            if period_start <= a.date <= period_end:
                if a.fee_type == FeeType.MANAGEMENT:
                    report.total_management_fee += a.amount
                elif a.fee_type == FeeType.PERFORMANCE:
                    report.total_performance_fee += a.amount
                elif a.fee_type == FeeType.ADMINISTRATION:
                    report.total_administration_fee += a.amount
                elif a.fee_type == FeeType.CUSTODY:
                    report.total_custody_fee += a.amount
                elif a.fee_type == FeeType.SUBSCRIPTION:
                    report.total_subscription_fee += a.amount
                elif a.fee_type == FeeType.REDEMPTION:
                    report.total_redemption_fee += a.amount

        return report

    def get_accruals(self, fund_id: str) -> List[FeeAccrual]:
        """Get all fee accruals for a fund."""
        return self._accruals.get(fund_id, [])

    def get_accruals_by_type(self, fund_id: str, fee_type: FeeType) -> List[FeeAccrual]:
        """Get fee accruals filtered by type."""
        return [a for a in self._accruals.get(fund_id, []) if a.fee_type == fee_type]

    def total_accrued(self, fund_id: str) -> float:
        """Total accrued fees (unpaid)."""
        return sum(a.amount for a in self._accruals.get(fund_id, []))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _record(self, fund_id: str, accrual: FeeAccrual) -> None:
        if fund_id not in self._accruals:
            self._accruals[fund_id] = []
        self._accruals[fund_id].append(accrual)
