"""Fund Operation Layer.

Institutional fund operations: NAV, AUM, subscription/redemption,
cash management, fee engine, portfolio rebalancing, and accounting.

Components
----------
FundService : Unified fund operations orchestrator
NAVEngine : Daily NAV computation
AUMTracker : AUM history & growth tracking
SubscriptionEngine : Investor subscription lifecycle
RedemptionEngine : Investor redemption lifecycle
CashManager : Real-time cash position management
FeeEngine : Management fee + performance fee accrual
RebalanceEngine : Portfolio rebalancing plan generator
AccountingAdapter : Fund accounting report generation
"""

from services.fund.models import (
    Fund,
    InvestorAccount,
    SubscriptionOrder,
    RedemptionOrder,
    FeeSchedule,
    CashReserve,
    RebalancePlan,
    NAVRecord,
    SubscriptionStatus,
    RedemptionType,
    FeeType,
    CrystallizationMode,
    RebalanceTrigger,
    CashReserveCategory,
)

from services.fund.nav import NAVEngine, NAVComponent, NAVResult
from services.fund.aum import AUMTracker, AUMRecord
from services.fund.subscription import SubscriptionEngine, SubscriptionError
from services.fund.redemption import RedemptionEngine, RedemptionError
from services.fund.cash_manager import CashManager
from services.fund.fee_engine import FeeEngine, FeeAccrual, FeeReport
from services.fund.rebalance import RebalanceEngine
from services.fund.accounting import AccountingAdapter, AccountingReport
from services.fund.service import FundService

__all__ = [
    # Models
    "Fund",
    "InvestorAccount",
    "SubscriptionOrder",
    "RedemptionOrder",
    "FeeSchedule",
    "CashReserve",
    "RebalancePlan",
    "NAVRecord",
    "FeeAccrual",
    "FeeReport",
    "AUMRecord",
    "NAVComponent",
    "NAVResult",
    # Enums
    "SubscriptionStatus",
    "RedemptionType",
    "FeeType",
    "CrystallizationMode",
    "RebalanceTrigger",
    "CashReserveCategory",
    # Engines
    "NAVEngine",
    "AUMTracker",
    "SubscriptionEngine",
    "SubscriptionError",
    "RedemptionEngine",
    "RedemptionError",
    "CashManager",
    "FeeEngine",
    "RebalanceEngine",
    # Accounting
    "AccountingAdapter",
    "AccountingReport",
    # Service
    "FundService",
]
