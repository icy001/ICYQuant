"""Multi-Account Adapter Layer Gate - A-01 .. A-12 acceptance tests.

Each adapter (A-Share / Futures / US Equity / FX) must pass the same
unified contract: connect, health, account, balance, positions, orders,
executions, submit, cancel, sync and reconcile.
"""

from __future__ import annotations

import pytest

from apps.adapters import (
    AshareAdapter,
    Broker,
    FxAdapter,
    FuturesAdapter,
    OrderIntent,
    UsEquityAdapter,
    service,
)
from apps.adapters.domain import Account, Market
from apps.adapters.routing import RoutingError


# ---------------------------------------------------------------------------
# A-01 / A-02  Account & Broker Domain
# ---------------------------------------------------------------------------


def test_a01_account_domain():
    account = Account(
        account_id="a1",
        broker_id="b1",
        broker_name="Broker",
        market=Market.US_EQUITY,
        currency="USD",
    )
    # unified model carries every field the spec defines
    for field in (
        "account_id",
        "broker_id",
        "market",
        "currency",
        "status",
        "equity",
        "cash",
        "buying_power",
        "margin",
        "positions",
        "orders",
        "capabilities",
    ):
        assert hasattr(account, field), f"Account missing field: {field}"
    # live snapshot fields are populated by the adapter after a sync
    account.equity = 100.0
    account.cash = 50.0
    account.buying_power = 50.0
    account.margin = 10.0
    assert account.equity == 100.0


def test_a02_broker_domain():
    broker = Broker(
        broker_id="b1",
        broker_name="Broker",
        market=Market.CN_STOCK,
        adapter_type="broker_adapter",
        capabilities={"submit_order", "cancel_order"},
        account_ids=["a1", "a2"],
    )
    for field in (
        "broker_id",
        "broker_name",
        "market",
        "adapter_type",
        "connection_status",
        "capabilities",
        "account_ids",
    ):
        assert hasattr(broker, field), f"Broker missing field: {field}"
    assert broker.account_ids == ["a1", "a2"]
    # a broker can own multiple accounts
    assert len(broker.account_ids) == 2


# ---------------------------------------------------------------------------
# A-03  Routing
# ---------------------------------------------------------------------------


def test_a03_routing_routes_intent_to_market_account():
    service.ensure_seeded()
    intent = OrderIntent(
        strategy_id="S1",
        symbol="EURUSD",
        market=Market.FX,
        side="BUY",
        quantity=10000,
        price=1.087,
    )
    broker_id, account_id = service.router.route(intent, service.registry)
    assert account_id == "fx_main"
    assert broker_id == "fx-demo"

    # explicit account target is honoured
    intent2 = OrderIntent(
        strategy_id="S1",
        symbol="AAPL",
        market=Market.US_EQUITY,
        side="BUY",
        quantity=10,
        price=178.5,
        account_id="us_main",
    )
    broker_id, account_id = service.router.route(intent2, service.registry)
    assert account_id == "us_main"

    # market mismatch is rejected
    with pytest.raises(RoutingError):
        service.router.route(
            OrderIntent(
                strategy_id="S1",
                symbol="EURUSD",
                market=Market.CN_STOCK,
                side="BUY",
                quantity=1000,
                price=1.0,
            ),
            service.registry,
        )


# ---------------------------------------------------------------------------
# A-04 .. A-07  Adapter Contract Tests
# ---------------------------------------------------------------------------


def _run_contract(adapter) -> None:
    account_id = adapter.account_ids[0]
    symbol = adapter.symbols()[0]
    price = adapter.reference_price(symbol)

    # connect / health
    assert adapter.connect() == "CONNECTED"
    health = adapter.health()
    assert health["status"] == "UP"
    assert health["market"] == adapter.market

    # account / balance
    account = adapter.get_account(account_id)
    assert account.market == adapter.market
    assert account.broker_id == adapter.broker_id
    balance = adapter.get_balance(account_id)
    assert balance.equity > 0
    assert balance.cash >= 0
    assert balance.buying_power >= 0

    # positions / orders / executions are present (seeded state)
    positions = adapter.get_positions(account_id)
    assert positions
    orders = adapter.get_orders(account_id)
    assert orders
    executions = adapter.get_executions(account_id)
    assert executions

    # submit -> filled + execution + position update + cash movement
    quantity = {"CN_STOCK": 100, "CN_FUTURES": 1, "US_EQUITY": 1, "FX": 1000}[
        adapter.market
    ]
    before_cash = adapter.get_balance(account_id).cash
    order = adapter.submit_order(
        OrderIntent(
            strategy_id="CT",
            symbol=symbol,
            market=adapter.market,
            side="BUY",
            quantity=quantity,
            price=price,
            account_id=account_id,
        )
    )
    assert order.status == "FILLED", order
    assert order.filled_quantity == quantity
    assert any(e.order_id == order.order_id for e in adapter.get_executions(account_id))
    assert any(p.symbol == symbol for p in adapter.get_positions(account_id))
    assert adapter.get_balance(account_id).cash < before_cash

    # cancel -> seeded open order becomes CANCELLED
    open_order = next(
        o for o in adapter.get_orders(account_id)
        if o.status in ("CREATED", "SUBMITTED", "ACCEPTED")
    )
    cancelled = adapter.cancel_order(account_id, open_order.order_id)
    assert cancelled.status == "CANCELLED"

    # query_order round-trips
    assert adapter.query_order(account_id, order.order_id).order_id == order.order_id

    # sync surfaces return the pulled state
    synced = adapter.sync_account(account_id)
    assert synced.account_id == account_id
    assert len(adapter.sync_positions(account_id)) == len(positions)
    assert len(adapter.sync_orders(account_id)) == len(orders) + 1  # + submitted
    assert len(adapter.sync_executions(account_id)) == len(executions) + 1


def test_a04_ashare_adapter_contract():
    _run_contract(AshareAdapter())


def test_a05_futures_adapter_contract():
    _run_contract(FuturesAdapter())


def test_a06_us_equity_adapter_contract():
    _run_contract(UsEquityAdapter())


def test_a07_fx_adapter_contract():
    _run_contract(FxAdapter())


# ---------------------------------------------------------------------------
# A-08 .. A-11  Sync
# ---------------------------------------------------------------------------


def test_a08_account_sync():
    service.ensure_seeded()
    report = service.sync_all()
    assert report["accounts"] == 4
    assert report["positions"] > 0
    assert report["orders"] > 0
    assert report["executions"] > 0
    account = service.registry.get_account("ashare_main")
    assert account.equity > 0
    assert account.cash >= 0
    assert len(account.positions) > 0


def test_a09_position_sync():
    service.ensure_seeded()
    live = service.registry.adapter_for("ctp-demo").get_positions("futures_main")
    synced = service.sync.sync_positions("futures_main")
    assert len(synced) == len(live)
    assert all(p.account_id == "futures_main" for p in synced)


def test_a10_order_sync():
    service.ensure_seeded()
    adapter = service.registry.adapter_for("yl-global")
    before = len(adapter.get_orders("us_main"))
    adapter.submit_order(
        OrderIntent(
            strategy_id="SYNC",
            symbol="MSFT",
            market=Market.US_EQUITY,
            side="SELL",
            quantity=1,
            price=316.0,
            account_id="us_main",
        )
    )
    synced = service.sync.sync_orders("us_main")
    assert len(synced) == before + 1
    assert any(o.symbol == "MSFT" and o.strategy_id == "SYNC" for o in synced)


def test_a11_execution_sync():
    service.ensure_seeded()
    adapter = service.registry.adapter_for("fx-demo")
    before = len(adapter.get_executions("fx_main"))
    adapter.submit_order(
        OrderIntent(
            strategy_id="SYNC",
            symbol="GBPUSD",
            market=Market.FX,
            side="BUY",
            quantity=1000,
            price=1.262,
            account_id="fx_main",
        )
    )
    synced = service.sync.sync_executions("fx_main")
    assert len(synced) == before + 1


# ---------------------------------------------------------------------------
# A-12  Reconciliation
# ---------------------------------------------------------------------------


def test_a12_reconciliation():
    service.ensure_seeded()
    report = service.reconcile()
    assert report["status"] == "CONSISTENT"
    assert len(report["accounts"]) == 4
    assert all(r["status"] == "CONSISTENT" for r in report["accounts"])

    # force a cache mismatch -> the check must flag it
    account = service.registry.get_account("ashare_main")
    account.equity += 12345.0
    try:
        report2 = service.reconcile()
        assert report2["status"] == "INCONSISTENT"
        row = next(r for r in report2["accounts"] if r["account_id"] == "ashare_main")
        assert row["status"] == "INCONSISTENT"
        assert "equity" in row["differences"]
    finally:
        account.equity -= 12345.0
