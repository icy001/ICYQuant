"""Portfolio Store — manages portfolio data, positions, NAV, and cash records."""

import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AssetClass(Enum):
    EQUITY = "equity"
    ETF = "etf"
    BOND = "bond"
    COMMODITY = "commodity"
    FOREX = "forex"
    CRYPTO = "crypto"
    DERIVATIVE = "derivative"
    CASH = "cash"
    ALTERNATIVE = "alternative"


class Currency(Enum):
    CNY = "CNY"
    USD = "USD"
    HKD = "HKD"
    EUR = "EUR"
    JPY = "JPY"
    GBP = "GBP"


class PortfolioType(Enum):
    STOCK = "stock"
    ETF = "etf"
    CTA = "cta"
    ALPHA = "alpha"
    AI = "ai"
    HYBRID = "hybrid"
    FUND_OF_FUNDS = "fof"
    MARKET_NEUTRAL = "market_neutral"
    MULTI_ASSET = "multi_asset"


@dataclass
class StoreConfig:
    """Configuration for portfolio store."""

    store_backend: str = "memory"  # memory | redis | database
    redis_url: str = ""
    db_connection_string: str = ""
    cache_ttl_seconds: int = 60
    max_positions_per_portfolio: int = 500
    enable_snapshots: bool = True
    snapshot_retention_days: int = 365


@dataclass
class PositionRecord:
    """A single position in a portfolio."""

    position_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    symbol: str = ""
    asset_class: AssetClass = AssetClass.EQUITY
    quantity: float = 0.0
    avg_cost: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    weight: float = 0.0
    currency: Currency = Currency.CNY
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    sector: str = ""
    strategy_id: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def pnl_total(self) -> float:
        return self.unrealized_pnl + self.realized_pnl

    @property
    def pnl_pct(self) -> float:
        cost = self.quantity * self.avg_cost
        return (self.pnl_total / cost * 100) if cost != 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "asset_class": self.asset_class.value,
            "quantity": self.quantity,
            "avg_cost": self.avg_cost,
            "current_price": self.current_price,
            "market_value": self.market_value,
            "weight": self.weight,
            "currency": self.currency.value,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "sector": self.sector,
            "strategy_id": self.strategy_id,
        }


@dataclass
class PortfolioRecord:
    """Portfolio-level aggregate record."""

    portfolio_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    portfolio_type: PortfolioType = PortfolioType.HYBRID
    base_currency: Currency = Currency.CNY
    nav: float = 0.0
    cash: float = 0.0
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    net_exposure: float = 0.0
    gross_exposure: float = 0.0
    leverage: float = 0.0
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    daily_return: float = 0.0
    cumulative_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    volatility: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0
    positions: List[PositionRecord] = field(default_factory=list)
    sub_portfolio_ids: List[str] = field(default_factory=list)
    benchmark_id: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def position_count(self) -> int:
        return len(self.positions)

    @property
    def equity(self) -> float:
        return self.nav - self.total_liabilities

    @property
    def net_asset_value(self) -> float:
        return self.nav

    def get_position_weights(self) -> Dict[str, float]:
        return {p.symbol: p.weight for p in self.positions}

    def get_sector_exposure(self) -> Dict[str, float]:
        exposure: Dict[str, float] = {}
        for pos in self.positions:
            sector = pos.sector or "unknown"
            exposure[sector] = exposure.get(sector, 0.0) + pos.weight
        return exposure

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "name": self.name,
            "portfolio_type": self.portfolio_type.value,
            "base_currency": self.base_currency.value,
            "nav": self.nav,
            "cash": self.cash,
            "total_assets": self.total_assets,
            "total_liabilities": self.total_liabilities,
            "net_exposure": self.net_exposure,
            "gross_exposure": self.gross_exposure,
            "leverage": self.leverage,
            "daily_pnl": self.daily_pnl,
            "total_pnl": self.total_pnl,
            "daily_return": self.daily_return,
            "cumulative_return": self.cumulative_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "volatility": self.volatility,
            "var_95": self.var_95,
            "cvar_95": self.cvar_95,
            "position_count": self.position_count,
            "positions": [p.to_dict() for p in self.positions],
        }


@dataclass
class AccountRecord:
    """Trading account record linked to portfolios."""

    account_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    account_name: str = ""
    account_type: str = ""  # individual | institutional | fund
    currency: Currency = Currency.CNY
    balance: float = 0.0
    available_cash: float = 0.0
    frozen_cash: float = 0.0
    margin_used: float = 0.0
    margin_limit: float = 0.0
    portfolio_ids: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @property
    def margin_ratio(self) -> float:
        return (self.margin_used / self.margin_limit) if self.margin_limit > 0 else 0.0


class PortfolioStore:
    """Central store for portfolio and position data.

    Manages CRUD operations for portfolios, positions, and accounts.
    Supports in-memory, Redis, and database backends.
    """

    def __init__(self, config: Optional[StoreConfig] = None):
        self.config = config or StoreConfig()
        self._portfolios: Dict[str, PortfolioRecord] = {}
        self._accounts: Dict[str, AccountRecord] = {}
        self._snapshots: Dict[str, List[Dict[str, Any]]] = {}
        self._cache: Dict[str, Tuple[float, Any]] = {}

    # ---- Portfolio CRUD ----

    def create_portfolio(self, portfolio: PortfolioRecord) -> PortfolioRecord:
        if not portfolio.portfolio_id:
            portfolio.portfolio_id = str(uuid.uuid4())[:8]
        self._portfolios[portfolio.portfolio_id] = portfolio
        logger.info("Portfolio created: %s (%s)", portfolio.name, portfolio.portfolio_id)
        return portfolio

    def get_portfolio(self, portfolio_id: str) -> Optional[PortfolioRecord]:
        return self._portfolios.get(portfolio_id)

    def list_portfolios(
        self, portfolio_type: Optional[PortfolioType] = None
    ) -> List[PortfolioRecord]:
        results = list(self._portfolios.values())
        if portfolio_type:
            results = [p for p in results if p.portfolio_type == portfolio_type]
        return results

    def update_portfolio(self, portfolio_id: str, **kwargs) -> Optional[PortfolioRecord]:
        p = self._portfolios.get(portfolio_id)
        if not p:
            return None
        for key, value in kwargs.items():
            if hasattr(p, key):
                setattr(p, key, value)
        p.updated_at = time.time()
        return p

    def delete_portfolio(self, portfolio_id: str) -> bool:
        if portfolio_id in self._portfolios:
            del self._portfolios[portfolio_id]
            return True
        return False

    # ---- Position Management ----

    def add_position(self, portfolio_id: str, position: PositionRecord) -> Optional[PositionRecord]:
        p = self._portfolios.get(portfolio_id)
        if not p:
            return None
        if len(p.positions) >= self.config.max_positions_per_portfolio:
            logger.warning("Max positions reached for portfolio %s", portfolio_id)
            return None
        position.updated_at = time.time()
        p.positions.append(position)
        self._recalculate_portfolio_metrics(p)
        return position

    def remove_position(self, portfolio_id: str, position_id: str) -> bool:
        p = self._portfolios.get(portfolio_id)
        if not p:
            return False
        before = len(p.positions)
        p.positions = [pos for pos in p.positions if pos.position_id != position_id]
        if len(p.positions) < before:
            self._recalculate_portfolio_metrics(p)
            return True
        return False

    def update_position(
        self, portfolio_id: str, position_id: str, **kwargs
    ) -> Optional[PositionRecord]:
        p = self._portfolios.get(portfolio_id)
        if not p:
            return None
        for pos in p.positions:
            if pos.position_id == position_id:
                for key, value in kwargs.items():
                    if hasattr(pos, key):
                        setattr(pos, key, value)
                pos.updated_at = time.time()
                self._recalculate_portfolio_metrics(p)
                return pos
        return None

    def get_positions(self, portfolio_id: str) -> List[PositionRecord]:
        p = self._portfolios.get(portfolio_id)
        return p.positions if p else []

    # ---- Account Management ----

    def create_account(self, account: AccountRecord) -> AccountRecord:
        if not account.account_id:
            account.account_id = str(uuid.uuid4())[:8]
        self._accounts[account.account_id] = account
        return account

    def get_account(self, account_id: str) -> Optional[AccountRecord]:
        return self._accounts.get(account_id)

    def list_accounts(self) -> List[AccountRecord]:
        return list(self._accounts.values())

    def get_accounts_for_portfolio(self, portfolio_id: str) -> List[AccountRecord]:
        return [
            acc for acc in self._accounts.values()
            if portfolio_id in acc.portfolio_ids
        ]

    # ---- Snapshot ----

    def save_snapshot(self, portfolio_id: str, snapshot: Dict[str, Any]) -> None:
        if portfolio_id not in self._snapshots:
            self._snapshots[portfolio_id] = []
        self._snapshots[portfolio_id].append(snapshot)

    def get_snapshots(self, portfolio_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        snapshots = self._snapshots.get(portfolio_id, [])
        return snapshots[-limit:] if limit > 0 else snapshots

    # ---- Internal ----

    def _recalculate_portfolio_metrics(self, portfolio: PortfolioRecord) -> None:
        total_mv = sum(p.market_value for p in portfolio.positions)
        portfolio.total_assets = total_mv + portfolio.cash
        portfolio.net_exposure = total_mv
        portfolio.gross_exposure = sum(abs(p.market_value) for p in portfolio.positions)
        portfolio.leverage = (
            portfolio.gross_exposure / portfolio.nav if portfolio.nav > 0 else 0.0
        )
        if total_mv > 0:
            for pos in portfolio.positions:
                pos.weight = pos.market_value / total_mv
        portfolio.updated_at = time.time()

    def get_summary(self) -> Dict[str, Any]:
        portfolios = list(self._portfolios.values())
        total_nav = sum(p.nav for p in portfolios)
        total_pnl = sum(p.total_pnl for p in portfolios)
        return {
            "total_portfolios": len(portfolios),
            "total_accounts": len(self._accounts),
            "total_nav": total_nav,
            "total_pnl": total_pnl,
            "avg_return": (
                sum(p.cumulative_return for p in portfolios) / len(portfolios)
                if portfolios else 0.0
            ),
        }
