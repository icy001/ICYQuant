"""Shared builders for the Commit 015 Account / Position Sync suites.

Everything here is deterministic on purpose:

* :class:`VirtualClock` drives ``now`` so §12 staleness and §13 latency are
  exact numbers instead of "roughly now";
* the broker fixtures speak the **vendor wire dialect** (Chinese keys,
  string numbers, a vendor ``更新时间``) so the normalizer is exercised
  rather than bypassed — the payloads are the same ones the simulated
  provider emits in production/dev;
* the default ledger is :func:`~services.account.sync.service.demo_ledger`,
  the very reader the API wires, so a suite asserting ``RECONCILED`` is
  testing the shipped wiring and not a convenient double.

Import it either way — the suites run both as loose files and inside a
package (same idiom as ``tests/market_data/adapters/broker_helpers.py``)::

    try:
        from .helpers import Harness
    except ImportError:  # pragma: no cover
        from helpers import Harness
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from services.account.domain.account import Account
from services.account.domain.enums import CST
from services.account.sync.config import AccountSyncConfig
from services.account.sync.ledger import LedgerBalance, LedgerPosition
from services.account.sync.repository import InMemoryAccountSnapshotRepository
from services.account.sync.service import AccountSyncService, demo_ledger
from services.account.sync.valuation import MappingPriceProvider, PositionValuator
from services.broker.account.broker_account import (
    ProviderBrokerAccountAdapter,
    SimulatedAccountProvider,
)

ACCOUNT_ID = "A001"

#: A-share morning session start — the wall clock every test begins at.
T0 = datetime(2026, 9, 15, 9, 30, 0, tzinfo=CST)

#: §13 — how far behind the broker's own timestamp ICYQuant reads it.
LATENCY_MS = 180.0

#: §18 — the prices the demo book is valued with.
PRICES = {"159852": "1.280", "159559": "0.820", "513050": "1.620"}

#: §18 — what :data:`PRICES` must produce for the demo book.
EXPECTED_POSITION_VALUES = {
    "159852": (Decimal("1.28"), Decimal("12800"), Decimal("300")),
    "159559": (Decimal("0.82"), Decimal("16400"), Decimal("400")),
    "513050": (Decimal("1.62"), Decimal("8100"), Decimal("100")),
}
EXPECTED_MARKET_VALUE = Decimal("37300")
EXPECTED_TOTAL_ASSET = Decimal("120800")

#: The demo book, in the order the provider reports it.
DEMO_SYMBOLS = ("159852", "159559", "513050")
DEMO_QUANTITIES = (Decimal("10000"), Decimal("20000"), Decimal("5000"))


class VirtualClock:
    """A tickable ``now_cst`` stand-in.

    Time is the one thing a sync test cannot afford to guess at: §13
    latency, §12 staleness and snapshot ordering are all durations, so the
    suite moves the clock by hand and asserts exact values.
    """

    def __init__(self, start: datetime = T0) -> None:
        self.value = start

    def __call__(self) -> datetime:
        return self.value

    def tick(self, seconds: float = 0.0, *, milliseconds: float = 0.0) -> datetime:
        self.value = self.value + timedelta(
            seconds=seconds, milliseconds=milliseconds
        )
        return self.value

    def set(self, moment: datetime) -> datetime:
        self.value = moment
        return self.value


def stamp(moment: datetime = T0) -> str:
    """The broker's own ``更新时间`` format (second resolution, no tz)."""
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def _apply(payload: dict, overrides: dict) -> dict:
    """Patch ``payload``; ``None`` deletes the key (brokers omit fields)."""
    for key, value in overrides.items():
        if value is None:
            payload.pop(key, None)
        else:
            payload[key] = value
    return payload


def account_payload(**overrides: Any) -> dict:
    """The demo balance in the *broker wire dialect*."""
    payload = {
        "币种": "CNY",
        "资金余额": "83500.00",
        "可用资金": "82000.00",
        "冻结资金": "1500.00",
        "证券市值": "128000.00",
        "总资产": "211500.00",
        "可买金额": "82000.00",
        "更新时间": stamp(),
    }
    return _apply(payload, overrides)


def position_payload(symbol: str = "159852", **overrides: Any) -> dict:
    """One position in the *broker wire dialect*."""
    row = {
        "证券代码": symbol,
        "市场": "SZ",
        "持仓数量": "10000",
        "可用数量": "10000",
        "冻结数量": "0",
        "成本价": "1.250",
        "现价": "1.280",
        "市值": "12800.00",
        "更新时间": stamp(),
    }
    return _apply(row, overrides)


def demo_position_payloads() -> list[dict]:
    """The three-row demo book, including the T+1 frozen leg (§19)."""
    return [
        position_payload("159852"),
        position_payload(
            "159559",
            **{
                "持仓数量": "20000",
                "可用数量": "0",
                "冻结数量": "20000",
                "成本价": "0.800",
                "现价": "0.820",
                "市值": "16400.00",
            },
        ),
        position_payload(
            "513050",
            **{
                "市场": "SH",
                "持仓数量": "5000",
                "可用数量": "5000",
                "冻结数量": "0",
                "成本价": "1.600",
                "现价": "1.620",
                "市值": "8100.00",
            },
        ),
    ]


def make_config(**overrides: Any) -> AccountSyncConfig:
    """An explicit config — never read the ambient environment."""
    payload = {
        "enabled": True,
        "provider": "simulated",
        "account_id": ACCOUNT_ID,
        "sync_interval_seconds": 10.0,
        "max_sync_age_seconds": 30.0,
        "valuation_enabled": True,
        "volume_in_lots": False,
        "strict_symbols": True,
    }
    payload.update(overrides)
    return AccountSyncConfig(**payload)


def ledger_position(
    symbol: str,
    quantity: Any = 10000,
    *,
    account_id: str = ACCOUNT_ID,
    available_quantity: Any = None,
    average_cost: Any = None,
    market_value: Any = None,
) -> LedgerPosition:
    return LedgerPosition(
        account_id=account_id,
        symbol=symbol,
        quantity=quantity,
        available_quantity=available_quantity,
        average_cost=average_cost,
        market_value=market_value,
    )


def demo_ledger_positions(account_id: str = ACCOUNT_ID) -> list[LedgerPosition]:
    """The ledger book that matches the demo broker book (PASS)."""
    return demo_ledger(account_id).positions(account_id)


_DEFAULT = object()


class Harness:
    """A wired §1 chain plus every moving part a test wants to poke.

    ``ledger`` defaults to the demo ledger (PASS); pass ``ledger=None`` to
    run without §9 reconciliation at all, or an
    :class:`InMemoryPositionLedgerReader` to script a mismatch.

    ``price_provider`` defaults to :data:`PRICES`; pass ``None`` for the
    "Market Data is unavailable" path (§18).
    """

    def __init__(
        self,
        *,
        config: AccountSyncConfig | None = None,
        provider: SimulatedAccountProvider | None = None,
        adapter: ProviderBrokerAccountAdapter | None = None,
        ledger: Any = _DEFAULT,
        price_provider: Any = _DEFAULT,
        repository: Any = None,
        account_id: str = ACCOUNT_ID,
        register: bool = True,
        service_clock: VirtualClock | None = None,
        provider_clock: VirtualClock | None = None,
        source: str = "BROKER",
        instruments: Any = None,
    ) -> None:
        self.account_id = account_id
        self.config = config or make_config()
        self.provider_clock = provider_clock or VirtualClock(T0)
        self.clock = service_clock or VirtualClock(
            T0 + timedelta(milliseconds=LATENCY_MS)
        )
        self.provider = provider or SimulatedAccountProvider(
            self.config, clock=self.provider_clock
        )
        self.adapter = adapter or ProviderBrokerAccountAdapter(
            self.provider, self.config
        )
        self.ledger = demo_ledger(account_id) if ledger is _DEFAULT else ledger
        if price_provider is _DEFAULT:
            price_provider = MappingPriceProvider(PRICES)
        self.price_provider = price_provider
        self.repository = repository or InMemoryAccountSnapshotRepository()
        self.service = AccountSyncService(
            self.adapter,
            self.repository,
            config=self.config,
            ledger=self.ledger,
            valuator=PositionValuator(
                price_provider, enabled=self.config.valuation_enabled
            ),
            clock=self.clock,
            instruments=instruments,
            source=source,
        )
        if register:
            self.register()

    # ── wiring helpers ────────────────────────────────────────────────

    def register(self, account_id: str | None = None) -> Account:
        target = account_id or self.account_id
        return self.service.register_account(
            Account(
                account_id=target,
                name="Simulated A-share account",
                broker=self.config.provider,
                currency="CNY",
            )
        )

    def connect(self) -> None:
        self.service.connect()

    def sync(self, account_id: str | None = None, *, connect: bool = True):
        if connect and not self.service.is_connected():
            self.service.connect()
        return self.service.sync(account_id or self.account_id)

    # ── readers ───────────────────────────────────────────────────────

    def latest(self):
        return self.repository.latest(self.account_id)

    def positions_by_symbol(self) -> dict:
        return {p.symbol: p for p in self.service.positions(self.account_id)}

    # ── ledger scripting (§9 — the ledger drifts, never the broker) ────

    def set_ledger_positions(self, rows: list[LedgerPosition]) -> None:
        self.ledger.set_positions(self.account_id, rows)

    def set_ledger_balance(self, balance: LedgerBalance) -> None:
        self.ledger.set_balance(self.account_id, balance)

    def ledger_drifts(self, symbol: str = "159852", **changes: Any) -> LedgerPosition:
        """Move *one* ledger row, leaving the broker book untouched."""
        rows = list(self.ledger.positions(self.account_id))
        for index, row in enumerate(rows):
            if row.symbol == symbol:
                rows[index] = LedgerPosition(
                    account_id=row.account_id,
                    symbol=row.symbol,
                    quantity=changes.get("quantity", row.quantity),
                    available_quantity=changes.get(
                        "available_quantity", row.available_quantity
                    ),
                    average_cost=changes.get("average_cost", row.average_cost),
                    market_value=changes.get("market_value", row.market_value),
                )
                break
        else:  # pragma: no cover - only on a typo in a test
            raise AssertionError(f"{symbol} is not in the ledger book")
        self.set_ledger_positions(rows)
        return rows[index]

    def restore_ledger(self) -> None:
        self.set_ledger_positions(demo_ledger_positions(self.account_id))


def make_normalizer(**config_overrides: Any):
    """A normalizer alone, for the §1 mapping suites."""
    from services.broker.account.normalizer import AccountNormalizer
    from services.market_data.universe import universe

    return AccountNormalizer(
        make_config(**config_overrides),
        instruments=universe,
        clock=VirtualClock(T0 + timedelta(milliseconds=LATENCY_MS)),
    )


__all__ = [
    "ACCOUNT_ID",
    "T0",
    "LATENCY_MS",
    "PRICES",
    "EXPECTED_POSITION_VALUES",
    "EXPECTED_MARKET_VALUE",
    "EXPECTED_TOTAL_ASSET",
    "DEMO_SYMBOLS",
    "DEMO_QUANTITIES",
    "VirtualClock",
    "Harness",
    "stamp",
    "account_payload",
    "position_payload",
    "demo_position_payloads",
    "make_config",
    "make_normalizer",
    "ledger_position",
    "demo_ledger_positions",
]
