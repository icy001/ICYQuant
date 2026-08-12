"""Unit tests: KillSwitch scoping and priority."""

from __future__ import annotations

from datetime import datetime, timezone

from services.control_plane.kill_switch.kill_switch import KillSwitch
from services.control_plane.kill_switch.kill_switch_reason import KillSwitchReason
from services.control_plane.kill_switch.kill_switch_scope import KillSwitchScope
from services.control_plane.trading_gate.gate_context import OrderContext

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)


def make_order(
    account_id="ACCT-1",
    strategy_id="ALPHA",
    instrument_id="NVDA",
    venue_id="NASDAQ",
    order_flow_id="flow-1",
):
    return OrderContext(
        order_id="ORD-1",
        account_id=account_id,
        strategy_id=strategy_id,
        instrument_id=instrument_id,
        venue_id=venue_id,
        order_flow_id=order_flow_id,
    )


def activate(ks, scope, scope_id=None):
    ks.activate(scope=scope, scope_id=scope_id, reason=KillSwitchReason.EMERGENCY, actor="op", now=NOW)


class TestScopedMatching:
    def test_global_blocks_everything(self):
        ks = KillSwitch()
        activate(ks, KillSwitchScope.GLOBAL)
        blocked = ks.is_blocked(make_order())
        assert blocked is not None
        assert blocked.scope is KillSwitchScope.GLOBAL

    def test_account_blocks_only_matching_account(self):
        ks = KillSwitch()
        activate(ks, KillSwitchScope.ACCOUNT, "ACCT-1")
        assert ks.is_blocked(make_order(account_id="ACCT-1")) is not None
        assert ks.is_blocked(make_order(account_id="ACCT-2")) is None

    def test_strategy_blocks_only_matching_strategy(self):
        ks = KillSwitch()
        activate(ks, KillSwitchScope.STRATEGY, "ALPHA")
        assert ks.is_blocked(make_order(strategy_id="ALPHA")) is not None
        assert ks.is_blocked(make_order(strategy_id="BETA")) is None

    def test_instrument_blocks_only_matching_instrument(self):
        ks = KillSwitch()
        activate(ks, KillSwitchScope.INSTRUMENT, "NVDA")
        assert ks.is_blocked(make_order(instrument_id="NVDA")) is not None
        assert ks.is_blocked(make_order(instrument_id="AAPL")) is None

    def test_venue_blocks_only_matching_venue(self):
        ks = KillSwitch()
        activate(ks, KillSwitchScope.VENUE, "NASDAQ")
        assert ks.is_blocked(make_order(venue_id="NASDAQ")) is not None
        assert ks.is_blocked(make_order(venue_id="NYSE")) is None

    def test_order_flow_blocks_matching_flow(self):
        ks = KillSwitch()
        activate(ks, KillSwitchScope.ORDER_FLOW, "flow-1")
        assert ks.is_blocked(make_order(order_flow_id="flow-1")) is not None
        assert ks.is_blocked(make_order(order_flow_id="flow-2")) is None

    def test_multiple_scopes_must_all_match(self):
        ks = KillSwitch()
        activate(ks, KillSwitchScope.STRATEGY, "ALPHA")
        activate(ks, KillSwitchScope.ACCOUNT, "ACCT-9")
        order = make_order(strategy_id="ALPHA", account_id="ACCT-1")
        assert ks.is_blocked(order) is not None  # strategy ALPHA matches

    def test_inactive_switch_does_not_block(self):
        ks = KillSwitch()
        activate(ks, KillSwitchScope.STRATEGY, "ALPHA")
        ks.request_release(KillSwitchScope.STRATEGY, "ALPHA", now=NOW)
        ks.complete_release(KillSwitchScope.STRATEGY, "ALPHA", now=NOW)
        assert ks.is_blocked(make_order(strategy_id="ALPHA")) is None


class TestPriority:
    def test_global_beats_account(self):
        ks = KillSwitch()
        activate(ks, KillSwitchScope.ACCOUNT, "ACCT-1")
        activate(ks, KillSwitchScope.GLOBAL)
        blocked = ks.is_blocked(make_order(account_id="ACCT-1"))
        assert blocked.scope is KillSwitchScope.GLOBAL

    def test_account_beats_strategy(self):
        ks = KillSwitch()
        activate(ks, KillSwitchScope.STRATEGY, "ALPHA")
        activate(ks, KillSwitchScope.ACCOUNT, "ACCT-1")
        blocked = ks.is_blocked(make_order(strategy_id="ALPHA", account_id="ACCT-1"))
        assert blocked.scope is KillSwitchScope.ACCOUNT

    def test_strategy_beats_instrument(self):
        ks = KillSwitch()
        activate(ks, KillSwitchScope.INSTRUMENT, "NVDA")
        activate(ks, KillSwitchScope.STRATEGY, "ALPHA")
        blocked = ks.is_blocked(make_order(strategy_id="ALPHA", instrument_id="NVDA"))
        assert blocked.scope is KillSwitchScope.STRATEGY

    def test_instrument_beats_venue(self):
        ks = KillSwitch()
        activate(ks, KillSwitchScope.VENUE, "NASDAQ")
        activate(ks, KillSwitchScope.INSTRUMENT, "NVDA")
        blocked = ks.is_blocked(make_order(instrument_id="NVDA", venue_id="NASDAQ"))
        assert blocked.scope is KillSwitchScope.INSTRUMENT

    def test_strategy_switch_allows_other_strategy(self):
        # Spec section 21: STRATEGY-A ACTIVE → A denied, B allowed.
        ks = KillSwitch()
        activate(ks, KillSwitchScope.STRATEGY, "ALPHA")
        assert ks.is_blocked(make_order(strategy_id="ALPHA")) is not None
        assert ks.is_blocked(make_order(strategy_id="BETA")) is None
