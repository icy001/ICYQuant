"""Fund Operation API — REST endpoints.

Endpoints
---------
GET    /api/v1/fund/{fund_id}              Fund info + snapshot
POST   /api/v1/fund/create                  Create a new fund
GET    /api/v1/fund/{fund_id}/nav           Latest NAV
POST   /api/v1/fund/{fund_id}/nav           Compute NAV
GET    /api/v1/fund/{fund_id}/aum           AUM summary
POST   /api/v1/fund/subscribe               Investor subscription
POST   /api/v1/fund/redeem                  Investor redemption
GET    /api/v1/fund/{fund_id}/cash          Cash position
GET    /api/v1/fund/{fund_id}/fees          Fee report
POST   /api/v1/fund/{fund_id}/rebalance     Generate rebalance plan
GET    /api/v1/fund/{fund_id}/reports       Audit package
GET    /api/v1/fund/{fund_id}/investors     Investor list
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from services.fund.models import (
    Fund,
    InvestorAccount,
    RedemptionType,
    RebalanceTrigger,
)
from services.fund.service import FundService
from services.fund.subscription import SubscriptionError
from services.fund.redemption import RedemptionError

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/fund", tags=["Fund Operations"])

# Singleton service instance
fund_service = FundService()

# Pre-create a demo fund for quick testing
_DEMO_FUND = Fund(
    fund_id="AI_GROWTH",
    fund_name="AI Growth Fund",
    nav=1.258,
    aum=523_000_000,
    total_shares=415_738_473.77,
    cash_balance=30_000_000,
)


# ---------------------------------------------------------------------------
# Fund CRUD
# ---------------------------------------------------------------------------


@router.get("/{fund_id}", summary="Get fund information and snapshot")
async def get_fund(fund_id: str):
    """Retrieve fund details and current operational snapshot.

    Example response::

        {
          "fund": {"fund_id": "AI_GROWTH", "nav": 1.258, "aum": 523000000, ...},
          "cash": {"total": 30000000, "available": 25000000, ...},
          "aum": {"current_aum": 523000000, "30d_growth_rate_pct": 12.5, ...},
          "investor_count": 3,
          ...
        }
    """
    # For demo, use the pre-created fund. In production, lookup from store.
    fund = _DEMO_FUND if fund_id == "AI_GROWTH" else Fund(
        fund_id=fund_id, fund_name=fund_id
    )
    # Ensure cash is initialized
    fund_service.cash.get(fund_id)
    snapshot = fund_service.get_fund_snapshot(fund)
    return snapshot


@router.post("/create", summary="Create a new fund", status_code=201)
async def create_fund(
    fund_id: str = Query(..., description="Unique fund identifier"),
    fund_name: str = Query(..., description="Fund display name"),
    initial_nav: float = Query(1.0, description="Initial NAV per share"),
    initial_cash: float = Query(0.0, description="Initial cash balance"),
    management_fee_rate: float = Query(0.015, description="Annual management fee (decimal)"),
    performance_fee_rate: float = Query(0.20, description="Performance fee rate (decimal)"),
    currency: str = Query("USD", description="Fund currency"),
):
    """Create a new fund with initial parameters."""
    fund = fund_service.create_fund(
        fund_id=fund_id,
        fund_name=fund_name,
        initial_nav=initial_nav,
        initial_cash=initial_cash,
        management_fee_rate=management_fee_rate,
        performance_fee_rate=performance_fee_rate,
        currency=currency,
    )
    return fund.to_dict()


# ---------------------------------------------------------------------------
# NAV
# ---------------------------------------------------------------------------


@router.get("/{fund_id}/nav", summary="Get latest NAV")
async def get_nav(fund_id: str):
    """Return the latest NAV record for the fund."""
    nav_history = fund_service.get_nav_history(fund_id)
    if not nav_history:
        raise HTTPException(status_code=404, detail="No NAV records found")
    return nav_history[-1].to_dict()


@router.post("/{fund_id}/nav", summary="Compute and record daily NAV")
async def compute_nav(
    fund_id: str,
    portfolio_value: float = Query(..., description="Total portfolio market value"),
    cash: float = Query(0.0, description="Cash balance"),
    receivables: float = Query(0.0),
    payables: float = Query(0.0),
    accrued_management_fee: float = Query(0.0),
    accrued_performance_fee: float = Query(0.0),
):
    """Compute NAV for the fund and record it.

    Example::

        POST /api/v1/fund/AI_GROWTH/nav?portfolio_value=500000000&cash=30000000
    """
    fund = _DEMO_FUND if fund_id == "AI_GROWTH" else Fund(fund_id=fund_id, fund_name=fund_id)
    cash_reserve = fund_service.cash.get(fund_id)

    result = fund_service.compute_nav(
        fund=fund,
        portfolio_value=portfolio_value,
        cash_reserve=cash_reserve,
        receivables=receivables,
        payables=payables,
        accrued_management_fee=accrued_management_fee,
        accrued_performance_fee=accrued_performance_fee,
    )
    record = fund_service.apply_nav(fund, result)
    return record.to_dict()


# ---------------------------------------------------------------------------
# AUM
# ---------------------------------------------------------------------------


@router.get("/{fund_id}/aum", summary="Get AUM summary")
async def get_aum(fund_id: str):
    """Return AUM summary including growth rate and flows."""
    summary = fund_service.get_aum_summary(fund_id)
    return summary


# ---------------------------------------------------------------------------
# Subscription / Redemption
# ---------------------------------------------------------------------------


@router.post("/subscribe", summary="Process fund subscription", status_code=201)
async def subscribe(
    fund_id: str = Query(..., description="Fund ID"),
    investor_name: str = Query(..., description="Investor name"),
    amount: float = Query(..., gt=0, description="Subscription amount"),
):
    """Process an investor subscription.

    Example request::

        POST /api/v1/fund/subscribe?fund_id=AI_GROWTH&investor_name=张三&amount=1000000

    Example response::

        {
          "order_id": "SUB_A1B2C3D4E5F6",
          "shares_allocated": 794912.56,
          "status": "SETTLED",
          "nav": 1.258
        }
    """
    fund = _DEMO_FUND if fund_id == "AI_GROWTH" else Fund(fund_id=fund_id, fund_name=fund_id)
    cash = fund_service.cash.get(fund_id)

    account = InvestorAccount(
        fund_id=fund_id,
        investor_name=investor_name,
    )

    try:
        order = fund_service.subscribe(fund=fund, account=account, amount=amount, cash=cash)
    except SubscriptionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        **order.to_dict(),
        "investor": account.to_dict(),
        "fund_nav": fund.nav,
        "fund_aum": fund.aum,
    }


@router.post("/redeem", summary="Process fund redemption", status_code=201)
async def redeem(
    fund_id: str = Query(..., description="Fund ID"),
    account_id: str = Query(..., description="Investor account ID"),
    shares: float = Query(..., gt=0, description="Shares to redeem"),
    redemption_type: str = Query("T1", description="Settlement type: T0, T1, T2, TN"),
):
    """Process an investor redemption.

    Example request::

        POST /api/v1/fund/redeem?fund_id=AI_GROWTH&account_id=INV_A1B2C3D4&shares=500000
    """
    fund = _DEMO_FUND if fund_id == "AI_GROWTH" else Fund(fund_id=fund_id, fund_name=fund_id)
    cash = fund_service.cash.get(fund_id)

    # Find investor account
    investors = fund_service._investors.get(fund_id, [])
    account = next((a for a in investors if a.account_id == account_id), None)
    if account is None:
        raise HTTPException(status_code=404, detail=f"Investor {account_id} not found")

    rtype = RedemptionType(redemption_type.upper())

    try:
        order = fund_service.redeem(
            fund=fund, account=account, shares=shares, cash=cash, redemption_type=rtype,
        )
    except RedemptionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        **order.to_dict(),
        "investor": account.to_dict(),
        "fund_nav": fund.nav,
        "fund_aum": fund.aum,
    }


# ---------------------------------------------------------------------------
# Cash
# ---------------------------------------------------------------------------


@router.get("/{fund_id}/cash", summary="Get cash position")
async def get_cash(fund_id: str):
    """Return detailed cash position breakdown.

    Example response::

        {
          "total": 30000000,
          "available": 25000000,
          "frozen": 5000000,
          "pending_redemption": 0,
          "fee_reserve": 0,
          "margin": 0
        }
    """
    summary = fund_service.get_cash_summary(fund_id)
    return summary


# ---------------------------------------------------------------------------
# Fees
# ---------------------------------------------------------------------------


@router.get("/{fund_id}/fees", summary="Get fee report")
async def get_fee_report(
    fund_id: str,
    start_date: Optional[str] = Query(None, description="Period start (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Period end (YYYY-MM-DD)"),
):
    """Get aggregated fee report for a period.

    Accrues daily management fee automatically when called.
    """
    fund = _DEMO_FUND if fund_id == "AI_GROWTH" else Fund(fund_id=fund_id, fund_name=fund_id)

    # Accrue today's management fee
    fund_service.accrue_daily_fees(fund)

    start = date.fromisoformat(start_date) if start_date else date.today().replace(day=1)
    end = date.fromisoformat(end_date) if end_date else date.today()

    report = fund_service.get_fee_report(fund_id, start, end)
    return report.to_dict()


# ---------------------------------------------------------------------------
# Rebalance
# ---------------------------------------------------------------------------


@router.post("/{fund_id}/rebalance", summary="Generate rebalance plan")
async def rebalance(
    fund_id: str,
    target_weights: str = Query(..., description="JSON: {\"strategy\": weight, ...}"),
    current_allocations: str = Query(..., description="JSON: {\"strategy\": notional, ...}"),
    new_cash: float = Query(0.0, description="New cash to deploy"),
    trigger: str = Query("SCHEDULED", description="Rebalance trigger type"),
):
    """Generate a portfolio rebalance plan.

    Example request::

        POST /api/v1/fund/AI_GROWTH/rebalance
          ?target_weights={"AI_Momentum":0.4,"Macro":0.3,"Cash":0.3}
          &current_allocations={"AI_Momentum":200000000,"Macro":150000000,"Cash":50000000}
          &new_cash=50000000
    """
    import json

    try:
        tw = json.loads(target_weights)
        ca = json.loads(current_allocations)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    fund = _DEMO_FUND if fund_id == "AI_GROWTH" else Fund(fund_id=fund_id, fund_name=fund_id)
    trig = RebalanceTrigger(trigger.upper())

    try:
        plan = fund_service.rebalance_portfolio(
            fund=fund,
            target_weights=tw,
            current_allocations=ca,
            new_cash=new_cash,
            trigger=trig,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return plan.to_dict()


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@router.get("/{fund_id}/reports", summary="Generate audit package")
async def get_reports(
    fund_id: str,
    start_date: str = Query(..., description="Period start (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Period end (YYYY-MM-DD)"),
):
    """Generate a complete audit package (NAV, holdings, cashflow, fees, investors).

    Requires NAV records to exist for the fund.
    """
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)

    # Need at least one NAV record
    nav_records = fund_service.get_nav_history(fund_id)
    if not nav_records:
        raise HTTPException(status_code=400, detail="No NAV records. Compute NAV first at POST /{fund_id}/nav")

    # Build simple allocations from the demo fund
    allocations = {
        "AI_Momentum": 200_000_000,
        "Macro": 150_000_000,
        "Cash": 50_000_000,
    }

    try:
        reports = fund_service.generate_audit_package(
            Fund(fund_id=fund_id, fund_name=fund_id, nav=1.258, aum=400_000_000),
            allocations=allocations,
            period_start=start,
            period_end=end,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"reports": [r.to_dict() for r in reports]}


# ---------------------------------------------------------------------------
# Investors
# ---------------------------------------------------------------------------


@router.get("/{fund_id}/investors", summary="List fund investors")
async def list_investors(fund_id: str):
    """Return all investor accounts for a fund."""
    fund = _DEMO_FUND if fund_id == "AI_GROWTH" else Fund(fund_id=fund_id, fund_name=fund_id)
    investors = fund_service._investors.get(fund_id, [])

    return {
        "fund_id": fund_id,
        "nav": fund.nav,
        "investor_count": len(investors),
        "investors": [
            {**inv.to_dict(), "current_value": inv.current_value(fund.nav), "pnl": inv.unrealized_pnl(fund.nav)}
            for inv in investors
        ],
    }
