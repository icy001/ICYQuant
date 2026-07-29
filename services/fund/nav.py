"""NAV (Net Asset Value) Engine.

Daily NAV calculation for fund operations.

Formula
-------
NAV = (Total Assets - Total Liabilities) / Total Shares

Assets include:
    - Portfolio market value (equities, bonds, derivatives)
    - Cash & cash equivalents
    - Accrued income (dividends, interest)
    - Receivables

Liabilities include:
    - Accrued fees (management, performance)
    - Payables (unsettled trades)
    - Borrowed funds / margin
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from services.fund.models import (
    CashReserve,
    Fund,
    NAVRecord,
)


@dataclass
class NAVComponent:
    """Breakdown of a single NAV component."""

    name: str
    value: float
    category: str  # "asset" | "liability"


@dataclass
class NAVResult:
    """Complete NAV computation result."""

    fund_id: str
    date: date
    nav_per_share: float
    total_net_asset: float
    total_shares: float

    assets: List[NAVComponent] = field(default_factory=list)
    liabilities: List[NAVComponent] = field(default_factory=list)

    total_assets: float = 0.0
    total_liabilities: float = 0.0
    accrued_management_fee: float = 0.0
    accrued_performance_fee: float = 0.0

    computed_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def net_asset(self) -> float:
        return self.total_assets - self.total_liabilities

    def to_dict(self) -> Dict[str, object]:
        return {
            "fund_id": self.fund_id,
            "date": self.date.isoformat(),
            "nav_per_share": self.nav_per_share,
            "total_net_asset": self.total_net_asset,
            "total_shares": self.total_shares,
            "total_assets": self.total_assets,
            "total_liabilities": self.total_liabilities,
            "net_asset": self.net_asset,
            "accrued_management_fee": self.accrued_management_fee,
            "accrued_performance_fee": self.accrued_performance_fee,
            "assets": [{"name": a.name, "value": a.value, "category": a.category} for a in self.assets],
            "liabilities": [{"name": l.name, "value": l.value, "category": l.category} for l in self.liabilities],
            "computed_at": self.computed_at.isoformat(),
        }


class NAVEngine:
    """Computes fund NAV from portfolio + cash + fee data.

    Usage::

        engine = NAVEngine()
        result = engine.compute(
            fund=fund,
            portfolio_value=500_000_000,
            cash=30_000_000,
            receivables=500_000,
            payables=200_000,
            accrued_mgmt_fee=20_548,
            accrued_perf_fee=0,
        )
    """

    def compute(
        self,
        fund: Fund,
        *,
        portfolio_value: float = 0.0,
        cash_reserve: Optional[CashReserve] = None,
        receivables: float = 0.0,
        payables: float = 0.0,
        accrued_dividends: float = 0.0,
        accrued_interest: float = 0.0,
        borrowed_funds: float = 0.0,
        accrued_management_fee: float = 0.0,
        accrued_performance_fee: float = 0.0,
        other_assets: Optional[List[Tuple[str, float]]] = None,
        other_liabilities: Optional[List[Tuple[str, float]]] = None,
    ) -> NAVResult:
        """Compute the fund's NAV.

        Parameters
        ----------
        fund : Fund
            The fund aggregate.
        portfolio_value : float
            Total market value of portfolio holdings.
        cash_reserve : CashReserve, optional
            Cash breakdown (total used if provided).
        receivables : float
            Unsettled sales, dividends receivable, etc.
        payables : float
            Unsettled purchases, expenses payable.
        accrued_dividends : float
            Dividends declared but not yet received.
        accrued_interest : float
            Interest accrued on cash / bonds.
        borrowed_funds : float
            Margin loans or other borrowings.
        accrued_management_fee : float
            Management fee accrued since last crystallisation.
        accrued_performance_fee : float
            Performance fee accrued since last crystallisation.
        other_assets : list of (name, value), optional
            Additional asset items.
        other_liabilities : list of (name, value), optional
            Additional liability items.

        Returns
        -------
        NAVResult
        """
        assets: List[NAVComponent] = []
        liabilities: List[NAVComponent] = []

        # -- Assets -----------------------------------------------------------
        assets.append(NAVComponent("Portfolio Holdings", portfolio_value, "asset"))

        cash_total = cash_reserve.total if cash_reserve else fund.cash_balance
        assets.append(NAVComponent("Cash", cash_total, "asset"))

        if receivables > 0:
            assets.append(NAVComponent("Receivables", receivables, "asset"))
        if accrued_dividends > 0:
            assets.append(NAVComponent("Accrued Dividends", accrued_dividends, "asset"))
        if accrued_interest > 0:
            assets.append(NAVComponent("Accrued Interest", accrued_interest, "asset"))
        if other_assets:
            for name, value in other_assets:
                assets.append(NAVComponent(name, value, "asset"))

        total_assets = sum(a.value for a in assets)

        # -- Liabilities ------------------------------------------------------
        if payables > 0:
            liabilities.append(NAVComponent("Payables", payables, "liability"))
        if borrowed_funds > 0:
            liabilities.append(NAVComponent("Borrowed Funds", borrowed_funds, "liability"))
        if accrued_management_fee > 0:
            liabilities.append(NAVComponent("Accrued Mgmt Fee", accrued_management_fee, "liability"))
        if accrued_performance_fee > 0:
            liabilities.append(NAVComponent("Accrued Perf Fee", accrued_performance_fee, "liability"))
        if other_liabilities:
            for name, value in other_liabilities:
                liabilities.append(NAVComponent(name, value, "liability"))

        total_liabilities = sum(l.value for l in liabilities)

        # -- Compute ----------------------------------------------------------
        net_asset = total_assets - total_liabilities
        total_shares = fund.total_shares if fund.total_shares > 0 else 1.0
        nav_per_share = net_asset / total_shares

        return NAVResult(
            fund_id=fund.fund_id,
            date=fund.nav_date,
            nav_per_share=round(nav_per_share, 6),
            total_net_asset=net_asset,
            total_shares=total_shares,
            assets=assets,
            liabilities=liabilities,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            accrued_management_fee=accrued_management_fee,
            accrued_performance_fee=accrued_performance_fee,
        )

    def apply_to_fund(self, fund: Fund, result: NAVResult) -> NAVRecord:
        """Update fund with NAV result and return an immutable record."""
        fund.update_nav(new_nav=result.nav_per_share, new_aum=result.total_net_asset)
        fund.cash_balance = result.total_assets - sum(
            a.value for a in result.assets if a.name != "Cash"
        )  # approximate cash

        return NAVRecord(
            fund_id=fund.fund_id,
            date=result.date,
            nav=result.nav_per_share,
            aum=result.total_net_asset,
            total_shares=result.total_shares,
            cash_balance=fund.cash_balance,
            management_fee_accrued=result.accrued_management_fee,
            performance_fee_accrued=result.accrued_performance_fee,
        )

    def quick_nav(self, fund: Fund, portfolio_value: float, cash: float) -> NAVResult:
        """Convenience: NAV with minimal inputs."""
        return self.compute(fund=fund, portfolio_value=portfolio_value, cash_reserve=CashReserve(total=cash))
