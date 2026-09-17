"""Shadow gate — every condition must pass before an order exists (Commit 016 §24).

The §24 checklist::

    Market Data      = HEALTHY        (feed READY + Commit 009 gate)
    Trading Session  = TRADABLE       (inside the Commit 009 session gate)
    Risk             = PASS           (shadow pre-trade checks)
    Account Sync     != ERROR         (broker reference not blocking)
    Reconciliation   != MISMATCH      (same reference, §11 semantics)
    Mode             = SHADOW         (by construction, never LIVE)

All of the market-data discipline (session / quality / lot size /
cache-degraded / lookahead, Commits 005–007) is **reused** through
``PaperMarketFeed.check_order`` — Shadow deliberately builds no second
market-data gate.  What this module adds is the shadow-specific ring:
mode, read-only account reference and pre-trade risk.

Fail-closed: an account reference that cannot answer counts as
blocked, because "could not verify the broker state" must never
degrade into "probably fine" (§13).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional

from services.market_data.paper import PaperFeedState, PaperOrderDecision
from services.trading.mode import TradingMode

from .shadow_config import ShadowConfig

logger = logging.getLogger(__name__)

_BPS = Decimal("10000")
_READY = PaperFeedState.READY.value


class ShadowGateReason(str, Enum):
    """Machine-readable Shadow block codes (§17 style)."""

    MODE_NOT_SHADOW = "SHADOW_MODE_NOT_SHADOW"
    UNKNOWN_ORDER_TYPE = "SHADOW_UNKNOWN_ORDER_TYPE"
    INVALID_QUANTITY = "SHADOW_INVALID_QUANTITY"
    FEED_NOT_READY = "SHADOW_FEED_NOT_READY"
    MARKET_GATE_BLOCKED = "SHADOW_MARKET_GATE_BLOCKED"
    ACCOUNT_SYNC_BLOCKED = "SHADOW_ACCOUNT_SYNC_BLOCKED"
    EXCESS_NOTIONAL = "SHADOW_EXCESS_NOTIONAL"
    SHORT_SELL_BLOCKED = "SHADOW_SHORT_SELL_BLOCKED"
    INSUFFICIENT_CASH = "SHADOW_INSUFFICIENT_CASH"


@dataclass(frozen=True)
class ShadowGateCheck:
    """One named §24 condition and whether it held."""

    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class ShadowGateDecision:
    """The single "may this Shadow order exist?" verdict.

    A blocked verdict is a first-class result carrying the machine
    reason plus the full check trail — never a bare ``False``.
    """

    allowed: bool
    reason: Optional[str] = None
    checks: tuple = field(default_factory=tuple)
    #: The embedded Commit 009 verdict (market-data side of the story).
    paper_decision: Optional[PaperOrderDecision] = None

    def as_dict(self) -> dict:
        paper = self.paper_decision.as_dict() if self.paper_decision else None
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "checks": [
                {"name": c.name, "passed": c.passed, "detail": c.detail}
                for c in self.checks
            ],
            "paper_decision": paper,
        }


def _feed_state_value(feed) -> str:
    state = getattr(feed, "state", None)
    if state is None:
        return "UNKNOWN"
    return str(getattr(state, "value", state))


class ShadowGate:
    """§24 — the ring around the reused Commit 009 market-data gate."""

    def __init__(
        self,
        *,
        feed,
        account,
        positions,
        mode: TradingMode = TradingMode.SHADOW,
        account_reference=None,
        config: Optional[ShadowConfig] = None,
        clock=None,
    ) -> None:
        if mode is not TradingMode.SHADOW:
            # §4/§25 — code-level guard: there is no way to construct a
            # Shadow gate in LIVE (or PAPER) mode.
            raise ValueError(
                "ShadowGate may only run in TradingMode.SHADOW — "
                "LIVE execution is not implemented (Commit 016 §4)"
            )
        self._feed = feed
        self._account = account
        self._positions = positions
        self._ref = account_reference
        self._cfg = config or ShadowConfig()
        self._clock = clock

    @property
    def mode(self) -> TradingMode:
        return TradingMode.SHADOW

    @property
    def feed(self):
        return self._feed

    @property
    def config(self) -> ShadowConfig:
        return self._cfg

    # ── evaluation ─────────────────────────────────────────────

    def evaluate(self, intent) -> ShadowGateDecision:
        """Evaluate the §24 checklist for one order intent."""
        checks: list[ShadowGateCheck] = []

        def done(
            allowed: bool,
            reason: Optional[ShadowGateReason] = None,
            paper: Optional[PaperOrderDecision] = None,
        ) -> ShadowGateDecision:
            return ShadowGateDecision(
                allowed=allowed,
                reason=reason.value if isinstance(reason, ShadowGateReason) else reason,
                checks=tuple(checks),
                paper_decision=paper,
            )

        def ok(name: str, detail: str = "") -> None:
            checks.append(ShadowGateCheck(name, True, detail))

        def fail(name: str, detail: str = "") -> None:
            checks.append(ShadowGateCheck(name, False, detail))

        symbol = str(getattr(intent, "symbol", "") or "")
        side = str(getattr(intent, "side", "") or "").upper()
        quantity = int(getattr(intent, "quantity", 0) or 0)
        order_type = str(
            getattr(intent, "order_type", "MARKET") or "MARKET"
        ).upper()
        # intent.timestamp may be None; the paper gate treats it as "now".

        # 1 — §5: Commit 016 simulates MARKET orders only.
        if order_type != "MARKET":
            fail(
                "order_type",
                f"order type {order_type} is not supported in Commit 016",
            )
            return done(False, ShadowGateReason.UNKNOWN_ORDER_TYPE)

        # 2 — basic quantity sanity (lot size itself is the Instrument
        #     Master's job inside the paper gate, §11).
        if quantity <= 0:
            fail("quantity", f"quantity {quantity} must be positive")
            return done(False, ShadowGateReason.INVALID_QUANTITY)
        ok("quantity", f"{quantity} shares")

        # 3 — §13/§14: feed-level readiness.  A feed that is DEGRADED /
        #     BLOCKED / OFFLINE must never fill "against the last price".
        state = _feed_state_value(self._feed)
        if state != _READY:
            fail(
                "feed_state",
                f"feed state {state} does not allow shadow execution",
            )
            return done(False, ShadowGateReason.FEED_NOT_READY)
        ok("feed_state", state)

        # 4 — the reused Commit 009 stack: session (§12), quality
        #     (§13), lot size (§11), cache-degraded (§14), lookahead
        #     (§9), book pricing (§8).
        try:
            paper = self._feed.check_order(
                symbol,
                side=side,
                quantity=quantity,
                order_timestamp=getattr(intent, "timestamp", None),
            )
        except Exception:  # noqa: BLE001 — fail-closed, §13
            logger.exception("shadow gate: paper check_order raised")
            fail("market_data", "market-data gate raised")
            return done(False, ShadowGateReason.MARKET_GATE_BLOCKED)
        if not paper.allowed:
            fail("market_data", f"{paper.reason}: {paper.detail}")
            return done(False, ShadowGateReason.MARKET_GATE_BLOCKED, paper=paper)
        ok("market_data", "paper gate ok")

        # 5 — §24/§29: the read-only broker reference.  Account-sync
        #     ERROR or reconciliation MISMATCH blocks new Shadow orders.
        if self._ref is not None:
            try:
                blocked = bool(self._ref.new_orders_blocked())
            except Exception:  # noqa: BLE001 — fail-closed
                logger.exception("shadow gate: account reference failed")
                blocked = True
            if blocked:
                fail(
                    "account_reference",
                    "broker account reference blocks new orders "
                    "(sync ERROR or reconciliation MISMATCH)",
                )
                return done(
                    False, ShadowGateReason.ACCOUNT_SYNC_BLOCKED, paper=paper
                )
            ok("account_reference", "not blocking")

        # 6 — §24 Risk = PASS: shadow pre-trade checks against the
        #     shadow ledger (never the broker's).
        if paper.fill_price is None:
            fail("risk", "no reference price from the paper gate")
            return done(
                False, ShadowGateReason.MARKET_GATE_BLOCKED, paper=paper
            )
        ref_price = Decimal(paper.fill_price)
        notional = ref_price * quantity
        if notional > Decimal(str(self._cfg.max_order_notional)):
            fail(
                "risk",
                f"notional {notional} exceeds cap "
                f"{self._cfg.max_order_notional}",
            )
            return done(False, ShadowGateReason.EXCESS_NOTIONAL, paper=paper)
        if side == "SELL" and quantity > self._positions.quantity(symbol):
            fail(
                "risk",
                f"sell {quantity} exceeds shadow holding "
                f"{self._positions.quantity(symbol)} of {symbol}",
            )
            return done(False, ShadowGateReason.SHORT_SELL_BLOCKED, paper=paper)
        if side == "BUY":
            slip = Decimal(str(self._cfg.slippage_bps)) / _BPS
            comm = Decimal(str(self._cfg.commission_bps)) / _BPS
            cost = notional * (1 + slip) + notional * comm
            if cost > self._account.cash:
                fail(
                    "risk",
                    f"buy cost {cost} exceeds shadow cash "
                    f"{self._account.cash}",
                )
                return done(
                    False, ShadowGateReason.INSUFFICIENT_CASH, paper=paper
                )
        ok("risk", "pre-trade checks passed")

        return done(True, paper=paper)


__all__ = [
    "ShadowGate",
    "ShadowGateReason",
    "ShadowGateCheck",
    "ShadowGateDecision",
]
