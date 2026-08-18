"""Simulated broker adapter base - in-memory implementation of the unified
AccountAdapter contract.

A simulated adapter behaves like a real broker endpoint for the purposes of
the Contract Tests, the Dashboard and Paper Trading: it holds a price book,
applies slippage on fills, updates cash / positions / margin, and exposes
the full sync surface. A real broker adapter only needs to implement the
same interface against the real API.
"""

from __future__ import annotations

import itertools
import random
from datetime import datetime, timezone
from typing import Dict, List

from apps.adapters.domain import (
    Account,
    AccountBalance,
    AccountStatus,
    Capability,
    ConnectionStatus,
    ExecutionRecord,
    OrderIntent,
    OrderRecord,
    OrderStatus,
    Position,
)
from apps.adapters.interface import AccountAdapter, AdapterError

_TERMINAL = {OrderStatus.FILLED, OrderStatus.REJECTED, OrderStatus.CANCELLED}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SimulatedAdapter(AccountAdapter):
    """Base class for the four market adapters (A-Share / Futures / US / FX)."""

    # identity set by subclasses
    broker_id = ""
    broker_name = ""
    adapter_type = ""
    market = ""
    currency = "USD"
    slippage = 0.0005
    price_decimals = 2
    capabilities = set()
    # risk parameters (margin-based markets only)
    margin_rate: float = 0.0  # futures
    leverage: float = 1.0  # FX

    def __init__(
        self,
        accounts: Dict[str, tuple],
        price_book: Dict[str, float],
        seed_positions: Dict[str, List[dict]] = None,
        seed_orders: Dict[str, List[dict]] = None,
        seed_executions: Dict[str, List[dict]] = None,
    ) -> None:
        self._accounts: Dict[str, Account] = {}
        self._balances: Dict[str, AccountBalance] = {}
        self._positions: Dict[str, List[Position]] = {}
        self._orders: Dict[str, List[OrderRecord]] = {}
        self._executions: Dict[str, List[ExecutionRecord]] = {}
        self._cash: Dict[str, float] = {}
        self._price_book = dict(price_book)
        self._connection = ConnectionStatus.DISCONNECTED
        self._latency_ms = 8
        self._order_seq = itertools.count(1)
        self._exec_seq = itertools.count(1)

        for account_id, (name, equity, cash) in accounts.items():
            account = Account(
                account_id=account_id,
                broker_id=self.broker_id,
                broker_name=self.broker_name,
                market=self.market,
                currency=self.currency,
                status=AccountStatus.ACTIVE,
                name=name,
                capabilities=set(self.capabilities),
            )
            self._accounts[account_id] = account
            self._balances[account_id] = AccountBalance(
                account_id=account_id,
                equity=equity,
                cash=cash,
                buying_power=cash,
                currency=self.currency,
            )
            self._cash[account_id] = cash
            self._positions[account_id] = []
            self._orders[account_id] = []
            self._executions[account_id] = []

        for account_id, rows in (seed_positions or {}).items():
            for row in rows:
                self._positions[account_id].append(self._make_position(account_id, row))
        for account_id, rows in (seed_orders or {}).items():
            for row in rows:
                self._orders[account_id].append(self._make_order(account_id, row))
        for account_id, rows in (seed_executions or {}).items():
            for row in rows:
                self._executions[account_id].append(self._make_execution(account_id, row))

        for account_id in self._accounts:
            self._refresh_balance(account_id)

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    @property
    def account_ids(self) -> list:
        return list(self._accounts.keys())

    def reference_price(self, symbol: str) -> float:
        return self._price_book.get(symbol, 0.0)

    def symbols(self) -> list:
        return list(self._price_book.keys())

    def _margin_for(self, quantity: float, price: float) -> float:
        if self.margin_rate:
            return quantity * price * self.margin_rate
        if self.leverage > 1.0:
            return quantity * price / self.leverage
        return 0.0

    def _make_position(self, account_id: str, row: dict) -> Position:
        quantity = float(row["quantity"])
        price = float(row["average_price"])
        last = float(row.get("last_price", price))
        margin = self._margin_for(quantity, last) or None
        return Position(
            account_id=account_id,
            symbol=row["symbol"],
            market=self.market,
            side=row["side"],
            quantity=quantity,
            average_price=price,
            last_price=last,
            currency=self.currency,
            realized_pnl=float(row.get("realized_pnl", 0.0)),
            margin=margin,
        )

    def _make_order(self, account_id: str, row: dict) -> OrderRecord:
        return OrderRecord(
            order_id=row["order_id"],
            account_id=account_id,
            broker_id=self.broker_id,
            symbol=row["symbol"],
            side=row["side"],
            quantity=float(row["quantity"]),
            price=float(row["price"]),
            status=row.get("status", OrderStatus.FILLED),
            filled_quantity=float(row.get("filled_quantity", 0.0)),
            average_fill_price=float(row.get("average_fill_price", 0.0)),
            created_at=row.get("created_at", _now()),
            updated_at=row.get("updated_at", _now()),
            strategy_id=row.get("strategy_id", "SEED"),
            market=self.market,
            rejection_reason=row.get("rejection_reason", ""),
        )

    def _make_execution(self, account_id: str, row: dict) -> ExecutionRecord:
        return ExecutionRecord(
            execution_id=row["execution_id"],
            order_id=row["order_id"],
            account_id=account_id,
            broker_id=self.broker_id,
            symbol=row["symbol"],
            side=row["side"],
            fill_quantity=float(row["fill_quantity"]),
            fill_price=float(row["fill_price"]),
            slippage=float(row.get("slippage", 0.0)),
            timestamp=row.get("timestamp", _now()),
            market=self.market,
        )

    def _refresh_balance(self, account_id: str) -> None:
        positions = self._positions[account_id]
        market_value = sum(p.market_value for p in positions)
        margin = sum((p.margin or 0.0) for p in positions)
        cash = self._cash[account_id]
        equity = cash + market_value
        balance = self._balances[account_id]
        balance.equity = round(equity, 2)
        balance.cash = round(cash, 2)
        balance.margin = round(margin, 2)
        balance.buying_power = round(max(cash - margin, 0.0), 2)
        balance.daily_pnl = round(
            sum(p.unrealized_pnl for p in positions)
            + sum(p.realized_pnl for p in positions),
            2,
        )
        balance.total_pnl = balance.daily_pnl

        account = self._accounts[account_id]
        account.equity = balance.equity
        account.cash = balance.cash
        account.buying_power = balance.buying_power
        account.margin = balance.margin
        account.daily_pnl = balance.daily_pnl
        account.total_pnl = balance.total_pnl
        account.positions = list(positions)
        account.orders = list(self._orders[account_id])
        account.executions = list(self._executions[account_id])

    def _apply_fill(
        self, account_id: str, symbol: str, side: str, quantity: float, price: float
    ) -> None:
        positions = self._positions[account_id]
        existing = next(
            (p for p in positions if p.symbol == symbol and p.side == side), None
        )
        if existing is None:
            margin = self._margin_for(quantity, price) or None
            positions.append(
                Position(
                    account_id=account_id,
                    symbol=symbol,
                    market=self.market,
                    side=side,
                    quantity=quantity,
                    average_price=price,
                    last_price=price,
                    currency=self.currency,
                    margin=margin,
                )
            )
        else:
            old_qty = existing.quantity
            old_avg = existing.average_price
            new_qty = old_qty + quantity
            new_avg = (old_avg * old_qty + price * quantity) / new_qty
            existing.quantity = new_qty
            existing.average_price = round(new_avg, 6)
            existing.last_price = price
            if existing.margin is not None:
                existing.margin = self._margin_for(new_qty, price) or None

        # mark-to-market every position on the symbol
        for p in positions:
            if p.symbol == symbol:
                p.last_price = price
            p.market_value = round(p.quantity * p.last_price, 2)
            p.exposure = round(p.quantity * p.last_price, 2)
            p.unrealized_pnl = round((p.last_price - p.average_price) * p.quantity, 2)

        cash_delta = self._margin_for(quantity, price) or quantity * price
        if side == "BUY":
            self._cash[account_id] -= cash_delta
        else:
            self._cash[account_id] += cash_delta

    # ------------------------------------------------------------------
    # AccountAdapter implementation
    # ------------------------------------------------------------------

    def connect(self) -> str:
        self._connection = ConnectionStatus.CONNECTED
        return self._connection

    def disconnect(self) -> None:
        self._connection = ConnectionStatus.DISCONNECTED

    def health(self) -> dict:
        return {
            "status": "UP" if self._connection == ConnectionStatus.CONNECTED else "DOWN",
            "broker_id": self.broker_id,
            "broker_name": self.broker_name,
            "market": self.market,
            "latency_ms": self._latency_ms,
            "error": None,
        }

    def get_account(self, account_id: str) -> Account:
        return self._accounts[account_id]

    def get_balance(self, account_id: str) -> AccountBalance:
        return self._balances[account_id]

    def get_positions(self, account_id: str) -> list:
        return list(self._positions[account_id])

    def get_orders(self, account_id: str) -> list:
        return list(self._orders[account_id])

    def get_executions(self, account_id: str) -> list:
        return list(self._executions[account_id])

    def submit_order(self, intent: OrderIntent) -> OrderRecord:
        account_id = intent.account_id
        if not account_id or account_id not in self._accounts:
            raise AdapterError(f"Unknown account: {account_id}")
        if self._connection != ConnectionStatus.CONNECTED:
            raise AdapterError("Adapter not connected")
        if intent.market and intent.market != self.market:
            raise AdapterError(f"Market mismatch: {intent.market} != {self.market}")
        if Capability.SUBMIT_ORDER not in self.capabilities:
            raise AdapterError(f"{self.market} does not support submit_order")

        symbol = intent.symbol
        price = float(intent.price or self._price_book.get(symbol) or 1.0)
        quantity = float(intent.quantity)
        notional = quantity * price
        order_id = f"ORD-{self.market}-{next(self._order_seq):06d}"
        now = _now()
        order = OrderRecord(
            order_id=order_id,
            account_id=account_id,
            broker_id=self.broker_id,
            symbol=symbol,
            side=intent.side,
            quantity=quantity,
            price=round(price, self.price_decimals),
            status=OrderStatus.SUBMITTED,
            created_at=now,
            updated_at=now,
            strategy_id=intent.strategy_id,
            market=self.market,
        )

        balance = self._balances[account_id]
        if notional > balance.buying_power:
            order.status = OrderStatus.REJECTED
            order.rejection_reason = "Insufficient buying power"
            order.updated_at = _now()
            self._orders[account_id].append(order)
            self._refresh_balance(account_id)
            return order

        # simulated fill with market-appropriate slippage
        sign = 1.0 if intent.side == "BUY" else -1.0
        slip = self.slippage * sign * random.uniform(0.3, 1.0)
        fill_price = round(price * (1 + slip), self.price_decimals)

        order.status = OrderStatus.FILLED
        order.filled_quantity = quantity
        order.average_fill_price = fill_price
        order.updated_at = _now()
        self._orders[account_id].append(order)

        execution = ExecutionRecord(
            execution_id=f"EXEC-{self.market}-{next(self._exec_seq):06d}",
            order_id=order_id,
            account_id=account_id,
            broker_id=self.broker_id,
            symbol=symbol,
            side=intent.side,
            fill_quantity=quantity,
            fill_price=fill_price,
            slippage=round(slip, 6),
            timestamp=_now(),
            market=self.market,
        )
        self._executions[account_id].append(execution)
        self._apply_fill(account_id, symbol, intent.side, quantity, fill_price)
        self._refresh_balance(account_id)
        return order

    def cancel_order(self, account_id: str, order_id: str) -> OrderRecord:
        order = self.query_order(account_id, order_id)
        if order.status in _TERMINAL:
            raise AdapterError(f"Order {order_id} not cancellable (status={order.status})")
        order.status = OrderStatus.CANCELLED
        order.updated_at = _now()
        return order

    def query_order(self, account_id: str, order_id: str) -> OrderRecord:
        for order in self._orders[account_id]:
            if order.order_id == order_id:
                return order
        raise AdapterError(f"Order not found: {order_id}")

    def sync_account(self, account_id: str) -> Account:
        """Pull the latest broker snapshot into the cached Account."""
        self._refresh_balance(account_id)
        return self._accounts[account_id]

    def sync_positions(self, account_id: str) -> list:
        self._refresh_balance(account_id)
        return list(self._positions[account_id])

    def sync_orders(self, account_id: str) -> list:
        self._refresh_balance(account_id)
        return list(self._orders[account_id])

    def sync_executions(self, account_id: str) -> list:
        self._refresh_balance(account_id)
        return list(self._executions[account_id])
