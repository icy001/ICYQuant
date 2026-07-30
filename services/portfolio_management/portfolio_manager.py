"""Multi-Portfolio Manager — unified management of all portfolios and capital allocation tree.

Supports: Stock, ETF, CTA, Alpha, AI, Market-Neutral, Multi-Asset, FoF portfolios.
Hierarchy: Investor → Fund → Portfolio → Strategy → Execution.
"""

import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from infrastructure.portfolio.portfolio_store import (
    PortfolioStore, PortfolioRecord, PositionRecord, AssetClass, Currency, PortfolioType,
)

logger = logging.getLogger(__name__)


class PortfolioStatus(Enum):
    CREATED = "created"
    ACTIVE = "active"
    FUNDING = "funding"
    REBALANCING = "rebalancing"
    PAUSED = "paused"
    LIQUIDATING = "liquidating"
    CLOSED = "closed"
    SUSPENDED = "suspended"


class AllocationType(Enum):
    INVESTOR = "investor"
    FUND = "fund"
    PORTFOLIO = "portfolio"
    STRATEGY = "strategy"
    EXECUTION = "execution"


@dataclass
class AllocationNode:
    """A node in the capital allocation tree."""

    node_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    node_type: AllocationType = AllocationType.PORTFOLIO
    allocation_pct: float = 0.0
    allocated_capital: float = 0.0
    current_value: float = 0.0
    target_return: float = 0.0
    risk_budget: float = 0.0
    children: List["AllocationNode"] = field(default_factory=list)
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def child_count(self) -> int:
        return len(self.children)

    def get_total_allocated(self) -> float:
        return sum(c.allocated_capital for c in self.children)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "node_type": self.node_type.value,
            "allocation_pct": self.allocation_pct,
            "allocated_capital": self.allocated_capital,
            "current_value": self.current_value,
            "target_return": self.target_return,
            "risk_budget": self.risk_budget,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class AllocationTree:
    """Full capital allocation tree from investor to execution."""

    root_id: str = ""
    root: Optional[AllocationNode] = None
    nodes: Dict[str, AllocationNode] = field(default_factory=dict)
    total_capital: float = 0.0
    created_at: float = field(default_factory=time.time)

    def add_node(self, node: AllocationNode, parent_id: Optional[str] = None) -> AllocationNode:
        self.nodes[node.node_id] = node
        if parent_id and parent_id in self.nodes:
            node.parent_id = parent_id
            self.nodes[parent_id].children.append(node)
        elif self.root is None:
            self.root = node
            self.root_id = node.node_id
        return node

    def get_node(self, node_id: str) -> Optional[AllocationNode]:
        return self.nodes.get(node_id)

    def get_children(self, node_id: str) -> List[AllocationNode]:
        node = self.nodes.get(node_id)
        return node.children if node else []

    def get_path(self, node_id: str) -> List[AllocationNode]:
        """Get path from root to a node."""
        path = []
        current = self.nodes.get(node_id)
        while current:
            path.insert(0, current)
            current = self.nodes.get(current.parent_id) if current.parent_id else None
        return path

    def validate(self) -> List[str]:
        """Validate allocation tree: check all children sum to <= parent allocation."""
        errors = []
        for node in self.nodes.values():
            if node.children:
                child_sum = sum(c.allocation_pct for c in node.children)
                if child_sum > 100.01:
                    errors.append(
                        f"Node {node.name}: children allocation sum {child_sum}% exceeds 100%"
                    )
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root_id": self.root_id,
            "root": self.root.to_dict() if self.root else None,
            "total_capital": self.total_capital,
            "node_count": len(self.nodes),
        }


@dataclass
class PortfolioConfig:
    """Configuration for a managed portfolio."""

    name: str = ""
    portfolio_type: PortfolioType = PortfolioType.HYBRID
    base_currency: Currency = Currency.CNY
    initial_capital: float = 0.0
    benchmark_id: str = ""
    target_return_annual: float = 0.10  # 10% annual target
    risk_budget_annual: float = 0.15  # 15% annual volatility budget
    max_leverage: float = 1.0
    max_position_weight: float = 0.10  # 10% max per position
    max_sector_weight: float = 0.30  # 30% max per sector
    min_cash_weight: float = 0.01  # 1% minimum cash
    rebalance_threshold_pct: float = 5.0
    strategy_ids: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Portfolio:
    """A managed portfolio with state tracking."""

    portfolio_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    config: PortfolioConfig = field(default_factory=PortfolioConfig)
    status: PortfolioStatus = PortfolioStatus.CREATED
    record: Optional[PortfolioRecord] = None
    allocation_node_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    parent_fund_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def nav(self) -> float:
        return self.record.nav if self.record else 0.0

    @property
    def is_active(self) -> bool:
        return self.status == PortfolioStatus.ACTIVE


@dataclass
class PortfolioGroup:
    """A group of portfolios managed together (e.g., a fund)."""

    group_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    portfolios: List[Portfolio] = field(default_factory=list)
    allocation_tree: Optional[AllocationTree] = None
    total_nav: float = 0.0
    total_capital: float = 0.0
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_aggregate_metrics(self) -> Dict[str, Any]:
        if not self.portfolios:
            return {}
        total_nav = sum(p.nav for p in self.portfolios if p.record)
        navs = [p.nav for p in self.portfolios if p.record and p.nav > 0]
        returns = [p.record.cumulative_return for p in self.portfolios if p.record]
        return {
            "total_nav": total_nav,
            "portfolio_count": len(self.portfolios),
            "active_count": sum(1 for p in self.portfolios if p.is_active),
            "avg_cumulative_return": sum(returns) / len(returns) if returns else 0.0,
        }


class PortfolioManager:
    """Unified portfolio manager for institutional multi-portfolio management.

    Manages the entire portfolio lifecycle:
    - Creation & configuration
    - Capital allocation tree
    - Status management
    - Group operations
    - Cross-portfolio analytics
    """

    def __init__(self, store: Optional[PortfolioStore] = None):
        self.store = store or PortfolioStore()
        self._portfolios: Dict[str, Portfolio] = {}
        self._groups: Dict[str, PortfolioGroup] = {}
        self._allocation_trees: Dict[str, AllocationTree] = {}

    # ---- Portfolio CRUD ----

    def create_portfolio(self, config: PortfolioConfig) -> Portfolio:
        """Create a new portfolio with configuration."""
        # Create underlying record
        record = PortfolioRecord(
            name=config.name,
            portfolio_type=config.portfolio_type,
            base_currency=config.base_currency,
            nav=config.initial_capital,
            cash=config.initial_capital,
            benchmark_id=config.benchmark_id,
        )
        self.store.create_portfolio(record)

        portfolio = Portfolio(
            portfolio_id=record.portfolio_id,
            config=config,
            record=record,
            status=PortfolioStatus.CREATED,
        )
        self._portfolios[portfolio.portfolio_id] = portfolio
        logger.info("Portfolio created: %s (%s)", config.name, portfolio.portfolio_id)
        return portfolio

    def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        return self._portfolios.get(portfolio_id)

    def list_portfolios(
        self,
        portfolio_type: Optional[PortfolioType] = None,
        status: Optional[PortfolioStatus] = None,
    ) -> List[Portfolio]:
        results = list(self._portfolios.values())
        if portfolio_type:
            results = [p for p in results if p.config.portfolio_type == portfolio_type]
        if status:
            results = [p for p in results if p.status == status]
        return results

    def update_portfolio(self, portfolio_id: str, **kwargs) -> Optional[Portfolio]:
        portfolio = self._portfolios.get(portfolio_id)
        if not portfolio:
            return None
        for key, value in kwargs.items():
            if hasattr(portfolio.config, key):
                setattr(portfolio.config, key, value)
        portfolio.updated_at = time.time()
        return portfolio

    def delete_portfolio(self, portfolio_id: str) -> bool:
        portfolio = self._portfolios.pop(portfolio_id, None)
        if portfolio:
            self.store.delete_portfolio(portfolio_id)
            return True
        return False

    # ---- Status Management ----

    def activate_portfolio(self, portfolio_id: str) -> bool:
        portfolio = self._portfolios.get(portfolio_id)
        if not portfolio or portfolio.status != PortfolioStatus.CREATED:
            return False
        portfolio.status = PortfolioStatus.ACTIVE
        portfolio.updated_at = time.time()
        logger.info("Portfolio activated: %s", portfolio.config.name)
        return True

    def pause_portfolio(self, portfolio_id: str) -> bool:
        portfolio = self._portfolios.get(portfolio_id)
        if not portfolio or portfolio.status != PortfolioStatus.ACTIVE:
            return False
        portfolio.status = PortfolioStatus.PAUSED
        portfolio.updated_at = time.time()
        return True

    def close_portfolio(self, portfolio_id: str) -> bool:
        portfolio = self._portfolios.get(portfolio_id)
        if not portfolio:
            return False
        portfolio.status = PortfolioStatus.LIQUIDATING
        # In real system, would trigger liquidation workflow
        portfolio.status = PortfolioStatus.CLOSED
        portfolio.updated_at = time.time()
        logger.info("Portfolio closed: %s", portfolio.config.name)
        return True

    # ---- Position Management ----

    def add_position(self, portfolio_id: str, position: PositionRecord) -> Optional[PositionRecord]:
        portfolio = self._portfolios.get(portfolio_id)
        if not portfolio:
            return None

        # Enforce constraints
        if position.weight > portfolio.config.max_position_weight:
            logger.warning(
                "Position weight %.2f%% exceeds max %.2f%% for portfolio %s",
                position.weight * 100, portfolio.config.max_position_weight * 100,
                portfolio.config.name,
            )

        result = self.store.add_position(portfolio_id, position)
        if result:
            portfolio.updated_at = time.time()
        return result

    def get_positions(self, portfolio_id: str) -> List[PositionRecord]:
        return self.store.get_positions(portfolio_id)

    # ---- Allocation Tree ----

    def create_allocation_tree(self, root_name: str, total_capital: float) -> AllocationTree:
        tree = AllocationTree(total_capital=total_capital)
        root = AllocationNode(
            name=root_name,
            node_type=AllocationType.INVESTOR,
            allocation_pct=100.0,
            allocated_capital=total_capital,
        )
        tree.add_node(root)
        self._allocation_trees[tree.root_id] = tree
        return tree

    def add_allocation_node(
        self,
        tree_id: str,
        name: str,
        node_type: AllocationType,
        allocation_pct: float,
        parent_id: Optional[str] = None,
        target_return: float = 0.0,
        risk_budget: float = 0.0,
    ) -> Optional[AllocationNode]:
        tree = self._allocation_trees.get(tree_id)
        if not tree:
            return None

        parent_capital = tree.nodes[parent_id].allocated_capital if parent_id else tree.total_capital
        node = AllocationNode(
            name=name,
            node_type=node_type,
            allocation_pct=allocation_pct,
            allocated_capital=parent_capital * allocation_pct / 100.0,
            target_return=target_return,
            risk_budget=risk_budget,
        )
        tree.add_node(node, parent_id)
        return node

    def get_allocation_tree(self, tree_id: str) -> Optional[AllocationTree]:
        return self._allocation_trees.get(tree_id)

    # ---- Group Management ----

    def create_group(
        self, name: str, portfolio_ids: Optional[List[str]] = None
    ) -> PortfolioGroup:
        group = PortfolioGroup(name=name)
        if portfolio_ids:
            for pid in portfolio_ids:
                portfolio = self._portfolios.get(pid)
                if portfolio:
                    group.portfolios.append(portfolio)
                    portfolio.parent_fund_id = group.group_id
        self._groups[group.group_id] = group
        return group

    def get_group(self, group_id: str) -> Optional[PortfolioGroup]:
        return self._groups.get(group_id)

    def list_groups(self) -> List[PortfolioGroup]:
        return list(self._groups.values())

    # ---- Cross-Portfolio Analytics ----

    def get_total_aum(self) -> float:
        return sum(p.nav for p in self._portfolios.values() if p.record and p.nav > 0)

    def get_total_pnl(self) -> float:
        return sum(p.record.total_pnl for p in self._portfolios.values() if p.record)

    def get_sector_exposure_all(self) -> Dict[str, float]:
        exposure: Dict[str, float] = {}
        for portfolio in self._portfolios.values():
            if portfolio.record:
                for sector, weight in portfolio.record.get_sector_exposure().items():
                    exposure[sector] = exposure.get(sector, 0.0) + weight
        return exposure

    def get_asset_class_allocation(self) -> Dict[str, float]:
        allocation: Dict[str, float] = {}
        for portfolio in self._portfolios.values():
            ptype = portfolio.config.portfolio_type.value
            allocation[ptype] = allocation.get(ptype, 0.0) + (portfolio.nav or 0.0)
        total = sum(allocation.values()) or 1.0
        return {k: v / total * 100 for k, v in allocation.items()}

    def get_summary(self) -> Dict[str, Any]:
        portfolios = list(self._portfolios.values())
        active = sum(1 for p in portfolios if p.is_active)
        by_type: Dict[str, int] = {}
        for p in portfolios:
            t = p.config.portfolio_type.value
            by_type[t] = by_type.get(t, 0) + 1
        return {
            "total_portfolios": len(portfolios),
            "active_portfolios": active,
            "total_groups": len(self._groups),
            "total_aum": self.get_total_aum(),
            "total_pnl": self.get_total_pnl(),
            "portfolio_by_type": by_type,
            "allocation_trees": len(self._allocation_trees),
        }
