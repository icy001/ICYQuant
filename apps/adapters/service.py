"""Multi-Account Service - the façade the Dashboard API talks to.

Owns the registry (brokers + accounts), the router, the sync engine and
the reconciliation check. Everything exposed here is serializable JSON so
the Dashboard never touches broker internals.
"""

from __future__ import annotations

import random
from typing import Optional

from apps.adapters.adapters import AshareAdapter, FxAdapter, FuturesAdapter, UsEquityAdapter
from apps.adapters.domain import (
    MARKET_LABELS,
    Account,
    Broker,
    ExecutionRecord,
    Market,
    OrderIntent,
    OrderRecord,
    Position,
)
from apps.adapters.registry import AdapterRegistry
from apps.adapters.routing import OrderRouter
from apps.adapters.sync import SyncEngine

# Rough conversion for the global portfolio USD aggregate (demo rates).
FX_RATE = {"CNY": 0.139, "USD": 1.0}


class MultiAccountService:
    """Unified multi-account trading facade (read views + controlled ops)."""

    def __init__(self) -> None:
        self.registry = AdapterRegistry()
        self.router = OrderRouter()
        self.sync = SyncEngine(self.registry)
        self._seeded = False

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def ensure_seeded(self) -> None:
        """Register + connect the four simulated market adapters (idempotent)."""
        if self._seeded:
            return
        for adapter_cls in (AshareAdapter, FuturesAdapter, UsEquityAdapter, FxAdapter):
            self.registry.register_adapter(adapter_cls())
        self.registry.connect_all()
        self.sync.sync_all()
        self._seeded = True

    # ------------------------------------------------------------------
    # read views (serialized for the Dashboard)
    # ------------------------------------------------------------------

    def brokers(self) -> list:
        self.ensure_seeded()
        return [_broker_dict(b) for b in self.registry.brokers()]

    def accounts(self) -> list:
        self.ensure_seeded()
        out = []
        for account in self.registry.accounts():
            broker = self.registry.get_broker(account.broker_id)
            out.append(_account_dict(account, broker))
        return out

    def account_detail(self, account_id: str) -> Optional[dict]:
        self.ensure_seeded()
        account = self.registry.get_account(account_id)
        broker = self.registry.get_broker(account.broker_id)
        exposure = sum(p.exposure for p in account.positions)
        return {
            **_account_dict(account, broker),
            "positions": [_position_dict(p) for p in account.positions],
            "orders": [_order_dict(o) for o in account.orders],
            "executions": [_execution_dict(e) for e in account.executions],
            "exposure": round(exposure, 2),
        }

    def executions(self) -> list:
        self.ensure_seeded()
        out = []
        for account in self.registry.accounts():
            for e in account.executions:
                out.append(_execution_dict(e))
        out.sort(key=lambda e: e["timestamp"], reverse=True)
        return out

    def global_portfolio(self) -> dict:
        """Global portfolio across every account (multi-account core view)."""
        self.ensure_seeded()
        accounts = self.accounts()
        all_positions = []
        for account in self.registry.accounts():
            for p in account.positions:
                all_positions.append(_position_dict(p))

        def _usd(value: float, ccy: str) -> float:
            return value * FX_RATE.get(ccy, 1.0)

        total_equity = sum(_usd(a["equity"], a["currency"]) for a in accounts)
        total_cash = sum(_usd(a["cash"], a["currency"]) for a in accounts)
        gross_exposure = sum(_usd(p["exposure"], p["currency"]) for p in all_positions)
        daily_pnl = sum(_usd(a["daily_pnl"], a["currency"]) for a in accounts)
        total_pnl = sum(_usd(a["total_pnl"], a["currency"]) for a in accounts)
        drawdown = sum(_usd(a["drawdown"], a["currency"]) for a in accounts)

        market_exposure = {}
        currency_exposure = {}
        for p in all_positions:
            label = MARKET_LABELS.get(p["market"], p["market"])
            market_exposure[label] = market_exposure.get(label, 0.0) + _usd(
                p["exposure"], p["currency"]
            )
            currency_exposure[p["currency"]] = currency_exposure.get(
                p["currency"], 0.0
            ) + _usd(p["exposure"], p["currency"])

        return {
            "summary": {
                "total_equity_usd": round(total_equity, 2),
                "total_cash_usd": round(total_cash, 2),
                "gross_exposure_usd": round(gross_exposure, 2),
                "net_exposure_usd": round(gross_exposure, 2),
                "daily_pnl_usd": round(daily_pnl, 2),
                "total_pnl_usd": round(total_pnl, 2),
                "drawdown_usd": round(drawdown, 2),
            },
            "market_exposure": {k: round(v, 2) for k, v in market_exposure.items()},
            "currency_exposure": {k: round(v, 2) for k, v in currency_exposure.items()},
            "accounts": accounts,
            "positions": all_positions,
        }

    def health(self) -> list:
        self.ensure_seeded()
        return [
            self.registry.adapter_for(b.broker_id).health() for b in self.registry.brokers()
        ]

    # ------------------------------------------------------------------
    # operations
    # ------------------------------------------------------------------

    def submit_intent(self, intent: OrderIntent) -> dict:
        """Route an OrderIntent to an account and submit it (audited by API)."""
        self.ensure_seeded()
        broker_id, account_id = self.router.route(intent, self.registry)
        intent.account_id = account_id
        adapter = self.registry.adapter_for(broker_id)
        order = adapter.submit_order(intent)
        self.sync.sync_account(account_id)
        return {
            "broker_id": broker_id,
            "account_id": account_id,
            "order": _order_dict(order),
        }

    def random_intent(self, strategy_id: str = "DASHBOARD") -> OrderIntent:
        """Demo feeder intent across the four markets (routed on submit)."""
        adapter = random.choice(
            [AshareAdapter(), FuturesAdapter(), UsEquityAdapter(), FxAdapter()]
        )
        symbol = random.choice(adapter.symbols())
        price = adapter.reference_price(symbol)
        side = random.choice(["BUY", "SELL"])
        if adapter.market == Market.CN_STOCK:
            quantity = random.choice([100, 200, 500])
        elif adapter.market == Market.CN_FUTURES:
            quantity = random.choice([1, 2, 3, 5])
        elif adapter.market == Market.US_EQUITY:
            quantity = random.choice([10, 25, 50, 100])
        else:
            quantity = random.choice([10000, 25000, 50000])
        return OrderIntent(
            strategy_id=strategy_id,
            symbol=symbol,
            market=adapter.market,
            side=side,
            quantity=quantity,
            price=price,
        )

    def sync_all(self) -> dict:
        self.ensure_seeded()
        return self.sync.sync_all()

    def reconcile(self) -> dict:
        self.ensure_seeded()
        return self.sync.reconcile()


# ---------------------------------------------------------------------------
# serialization helpers
# ---------------------------------------------------------------------------


def _position_dict(p: Position) -> dict:
    return {
        "account_id": p.account_id,
        "symbol": p.symbol,
        "market": p.market,
        "market_label": MARKET_LABELS.get(p.market, p.market),
        "side": p.side,
        "quantity": p.quantity,
        "average_price": p.average_price,
        "last_price": p.last_price,
        "market_value": p.market_value,
        "unrealized_pnl": p.unrealized_pnl,
        "realized_pnl": p.realized_pnl,
        "exposure": p.exposure,
        "currency": p.currency,
        "margin": p.margin,
    }


def _order_dict(o: OrderRecord) -> dict:
    return {
        "order_id": o.order_id,
        "account_id": o.account_id,
        "broker_id": o.broker_id,
        "symbol": o.symbol,
        "market": o.market,
        "side": o.side,
        "quantity": o.quantity,
        "price": o.price,
        "status": o.status,
        "filled_quantity": o.filled_quantity,
        "average_fill_price": o.average_fill_price,
        "created_at": o.created_at,
        "updated_at": o.updated_at,
        "strategy_id": o.strategy_id,
        "rejection_reason": o.rejection_reason,
    }


def _execution_dict(e: ExecutionRecord) -> dict:
    return {
        "execution_id": e.execution_id,
        "order_id": e.order_id,
        "account_id": e.account_id,
        "broker_id": e.broker_id,
        "symbol": e.symbol,
        "market": e.market,
        "side": e.side,
        "fill_quantity": e.fill_quantity,
        "fill_price": e.fill_price,
        "slippage": e.slippage,
        "timestamp": e.timestamp,
    }


def _account_dict(account: Account, broker: Broker) -> dict:
    return {
        "account_id": account.account_id,
        "name": account.name,
        "broker_id": account.broker_id,
        "broker_name": account.broker_name,
        "market": account.market,
        "market_label": MARKET_LABELS.get(account.market, account.market),
        "currency": account.currency,
        "status": account.status,
        "connection": broker.connection_status,
        "equity": account.equity,
        "cash": account.cash,
        "buying_power": account.buying_power,
        "margin": account.margin,
        "daily_pnl": account.daily_pnl,
        "total_pnl": account.total_pnl,
        "drawdown": account.drawdown,
        "positions": len(account.positions),
        "orders": len(account.orders),
        "executions": len(account.executions),
        "capabilities": sorted(account.capabilities),
    }


def _broker_dict(broker: Broker) -> dict:
    return {
        "broker_id": broker.broker_id,
        "broker_name": broker.broker_name,
        "market": broker.market,
        "market_label": MARKET_LABELS.get(broker.market, broker.market),
        "adapter_type": broker.adapter_type,
        "connection_status": broker.connection_status,
        "capabilities": sorted(broker.capabilities),
        "account_ids": list(broker.account_ids),
    }


# ---------------------------------------------------------------------------
# module-level singleton (seeded lazily on first use)
# ---------------------------------------------------------------------------

service = MultiAccountService()
