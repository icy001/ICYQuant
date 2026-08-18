"""Golden Trading Scenarios - deterministic acceptance tests.

Scenario 01  Normal trade      : Signal -> Risk APPROVE -> Order -> Execution -> Position -> Ledger
Scenario 02  Risk reject       : Signal -> Risk REJECT -> END
Scenario 03  Order reject      : Signal -> Risk APPROVE -> Order -> Broker REJECT
Scenario 04  Partial fill      : Order=100 -> Fill=40 -> Fill=60 (no duplicate)
Scenario 05  Duplicate event   : ExecutionCreated x2 -> Position=1 (not 2)
Scenario 06  Event loss        : Order -> Execution -> [Position missing] -> Reconciliation INCONSISTENCY -> repair
Scenario 07  Service crash     : Order -> Execution -> crash -> restart -> replay -> rebuild -> reconcile
Scenario 08  Ledger mismatch   : Position=100 / Ledger=80 -> detect -> reconcile -> repair -> Position=Ledger

Each scenario returns (passed: bool, detail: str).
"""
from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import Callable

from apps.runtime.pipeline import Signal, TradingPipeline
from services.position.model import Position


@dataclass
class ScenarioResult:
    number: int
    name: str
    passed: bool
    detail: str = ""


ScenarioFn = Callable[[], ScenarioResult]


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


# ---------------------------------------------------------------------------
# Scenario 01 - Normal Trade
# ---------------------------------------------------------------------------
def scenario_01() -> ScenarioResult:
    p = TradingPipeline()
    sig = Signal(symbol="AAPL", side="BUY", quantity=100)
    r = p.submit_signal(sig)

    _check(r.risk_decision.get("approved") is True, "risk must approve")
    _check(r.order_id is not None, "order must exist")

    p.fill_order(r, 100, 150.5)

    order = p.order_manager.get_order(r.order_id)
    _check(order.status.value == "FILLED", f"order must be FILLED, got {order.status.value}")
    _check(r.filled_quantity == 100, f"execution must fill 100, got {r.filled_quantity}")

    total = sum(v.quantity for v in r.positions.values())
    _check(total == 100, f"position must be 100, got {total}")

    led = p.ledger["count"]
    _check(led == 1, f"ledger must have 1 entry, got {led}")

    rec = p.reconcile(r)
    _check(rec["status"] == "OK", f"reconcile must be OK, got {rec}")

    return ScenarioResult(1, "Normal Trade", True, "Order/Execution/Position/Ledger all correct")


# ---------------------------------------------------------------------------
# Scenario 02 - Risk Reject
# ---------------------------------------------------------------------------
def scenario_02() -> ScenarioResult:
    p = TradingPipeline()
    sig = Signal(symbol="AAPL", side="BUY", quantity=99999)
    r = p.submit_signal(sig)

    _check(r.risk_decision.get("approved") is False, "risk must reject")
    _check(r.order_id is None, "no order may be created")
    _check(len(r.positions) == 0, "position must be unchanged")
    _check(p.ledger["count"] == 0, "ledger must be unchanged")

    return ScenarioResult(2, "Risk Reject", True, "Order=0, Position unchanged, Ledger unchanged")


# ---------------------------------------------------------------------------
# Scenario 03 - Order Reject (broker)
# ---------------------------------------------------------------------------
def scenario_03() -> ScenarioResult:
    p = TradingPipeline()
    sig = Signal(symbol="AAPL", side="BUY", quantity=100)
    r = p.submit_signal(sig)

    _check(r.risk_decision.get("approved") is True, "risk must approve")

    p.reject_order(r, reason="broker_reject")

    order = p.order_manager.get_order(r.order_id)
    _check(order.status.value == "REJECTED", f"order must be REJECTED, got {order.status.value}")
    _check(len(r.positions) == 0, "position must be unchanged")
    _check(p.ledger["count"] == 0, "ledger must be unchanged")

    return ScenarioResult(3, "Order Reject", True, "Position unchanged, Ledger unchanged")


# ---------------------------------------------------------------------------
# Scenario 04 - Partial Fill (40 + 60, no duplicate)
# ---------------------------------------------------------------------------
def scenario_04() -> ScenarioResult:
    p = TradingPipeline()
    sig = Signal(symbol="AAPL", side="BUY", quantity=100)
    r = p.submit_signal(sig)

    p.fill_order(r, 40, 150.0)
    p.fill_order(r, 60, 152.0)

    order = p.order_manager.get_order(r.order_id)
    _check(order.status.value == "FILLED", f"order must be FILLED, got {order.status.value}")
    _check(r.filled_quantity == 100, f"filled must be exactly 100, got {r.filled_quantity}")

    total = sum(v.quantity for v in r.positions.values())
    _check(total == 100, f"position must be 100 (no duplicate), got {total}")

    led = p.ledger["count"]
    _check(led == 2, f"ledger must have exactly 2 fill entries (40+60), got {led}")

    rec = p.reconcile(r)
    _check(rec["status"] == "OK", f"reconcile must be OK, got {rec}")

    return ScenarioResult(4, "Partial Fill", True, "40+60=100, no duplicate, Position=100, Ledger=100")


# ---------------------------------------------------------------------------
# Scenario 05 - Duplicate Event (ExecutionCreated x2 -> Position=1)
# ---------------------------------------------------------------------------
def scenario_05() -> ScenarioResult:
    from services.oms.order.state_machine import InvalidTransitionError

    p = TradingPipeline()
    sig = Signal(symbol="AAPL", side="BUY", quantity=100)
    r = p.submit_signal(sig)

    # Broker delivers the same execution twice
    p.fill_order(r, 100, 150.5)
    duplicate_rejected = False
    try:
        p.fill_order(r, 100, 150.5)  # duplicate delivery
    except InvalidTransitionError:
        duplicate_rejected = True
    _check(duplicate_rejected, "duplicate fill must be rejected by order state machine")

    total = sum(v.quantity for v in r.positions.values())
    _check(total == 100, f"position must be exactly 1 (100 qty), got {total}")

    led = p.ledger["count"]
    _check(led == 1, f"ledger must have 1 entry (not 2), got {led}")

    return ScenarioResult(
        5, "Duplicate Event", True,
        "Duplicate fill rejected by state machine; Position=1, Ledger=1",
    )


# ---------------------------------------------------------------------------
# Scenario 06 - Event Loss -> Reconciliation INCONSISTENCY -> repair
# ---------------------------------------------------------------------------
def scenario_06() -> ScenarioResult:
    p = TradingPipeline()
    sig = Signal(symbol="AAPL", side="BUY", quantity=100)
    r = p.submit_signal(sig)

    # Order + Execution happen, but the Position event is "lost"
    p.fill_order(r, 100, 150.5, record_position=False)
    _check(len(r.positions) == 0, "position must be empty (simulated loss)")

    # Reconciliation must detect INCONSISTENCY
    rec = p.reconcile(r)
    _check(rec["status"] == "MISMATCH", f"reconciliation must detect MISMATCH, got {rec}")

    # Repair: rebuild position from ledger (official PositionRebuilder)
    from services.ledger.service.rebuilder import PositionRebuilder

    builder = PositionRebuilder()
    positions = builder.rebuild(p.ledger_store.all_events())
    _check(len(positions) > 0, "rebuild must restore position")

    total = sum(q for q in positions.values())
    _check(total == 100, f"rebuilt position must be 100, got {total}")

    return ScenarioResult(
        6, "Event Loss / Reconciliation", True,
        f"Detect INCONSISTENCY -> Rebuild -> Verify (restored {total})",
    )


# ---------------------------------------------------------------------------
# Scenario 07 - Service Crash -> Restart -> Replay -> Rebuild -> Reconcile
# ---------------------------------------------------------------------------
def scenario_07() -> ScenarioResult:
    p = TradingPipeline()
    sig = Signal(symbol="AAPL", side="BUY", quantity=100)
    r = p.submit_signal(sig)
    p.fill_order(r, 100, 150.5)
    expected_position = sum(v.quantity for v in r.positions.values())
    expected_ledger = p.ledger["count"]

    # CRASH: new runtime (fresh state) started from durable ledger stream
    p2 = TradingPipeline()
    _check(len(p2.position_repo.positions) == 0, "fresh runtime must have no positions")

    # Replay: replay ledger events into the new runtime
    from services.ledger.service.rebuilder import PositionRebuilder

    for event in p.ledger_store.all_events():
        p2.ledger_store.append(event)

    builder = PositionRebuilder()
    positions = builder.rebuild(p2.ledger_store.all_events())
    restored = sum(q for q in positions.values())

    # Write rebuilt positions back into the runtime repo, then reconcile
    for symbol, qty in positions.items():
        p2.position_repo.save(
            Position(
                position_id=symbol,
                account_id="SYSTEM",
                portfolio_id="SCENARIO",
                symbol=symbol,
                quantity=int(qty),
                avg_price=150.5,
                side="BUY",
            )
        )
    r.positions = dict(p2.position_repo.positions)

    # Reconciliation between rebuilt position and ledger
    rec = p2.reconcile(r)

    _check(restored == expected_position, f"rebuilt position {restored} != expected {expected_position}")
    _check(p2.ledger_store.count() == expected_ledger, "ledger event count must match after replay")
    _check(rec["status"] == "OK", f"post-crash reconcile must be OK, got {rec}")

    return ScenarioResult(
        7, "Service Crash Recovery", True,
        f"Restart -> Replay -> Rebuild (={restored}) -> Reconcile OK",
    )


# ---------------------------------------------------------------------------
# Scenario 08 - Ledger / Position Mismatch -> repair -> Position = Ledger
# ---------------------------------------------------------------------------
def scenario_08() -> ScenarioResult:
    p = TradingPipeline()
    sig = Signal(symbol="AAPL", side="BUY", quantity=100)
    r = p.submit_signal(sig)
    p.fill_order(r, 100, 150.5)
    _check(p.ledger["count"] == 1, "precondition: ledger has fill entry")

    # Tamper: delete the ledger event -> Position=100, Ledger=0 (mismatch)
    p.ledger_store.clear()
    rec = p.reconcile(r)
    _check(rec["status"] == "MISMATCH", f"must detect mismatch, got {rec}")

    # Repair: re-apply the trade so Ledger catches up to Position
    p.ledger_service.record_order_filled(
        user_id="SYSTEM",
        order_id=r.order_id,
        symbol=sig.symbol,
        side=sig.side,
        quantity=100,
        price=150.5,
    )
    rec2 = p.reconcile(r)
    _check(rec2["status"] == "OK", f"after repair reconcile must be OK, got {rec2}")
    _check(rec2["position"] == rec2["ledger"], f"Position({rec2['position']}) must equal Ledger({rec2['ledger']})")

    return ScenarioResult(
        8, "Ledger/Position Mismatch Repair", True,
        f"Detect -> Repair -> Verify (Position={rec2['position']} = Ledger={rec2['ledger']})",
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
SCENARIOS: list[tuple[int, str, ScenarioFn]] = [
    (1, "Normal Trade", scenario_01),
    (2, "Risk Reject", scenario_02),
    (3, "Order Reject", scenario_03),
    (4, "Partial Fill", scenario_04),
    (5, "Duplicate Event", scenario_05),
    (6, "Event Loss", scenario_06),
    (7, "Service Crash", scenario_07),
    (8, "Ledger Mismatch", scenario_08),
]


def run_all_scenarios() -> list[ScenarioResult]:
    results: list[ScenarioResult] = []
    for number, name, fn in SCENARIOS:
        try:
            result = fn()
        except AssertionError as exc:
            result = ScenarioResult(number, name, False, str(exc))
        except Exception as exc:  # noqa: BLE001
            result = ScenarioResult(number, name, False, f"unexpected error: {exc}")
            traceback.print_exc()
        results.append(result)
    return results


def summarize(results: list[ScenarioResult]) -> dict:
    passed = [r for r in results if r.passed]
    return {
        "total": len(results),
        "passed": len(passed),
        "failed": len(results) - len(passed),
        "gate": "PASS" if len(passed) == len(results) else "FAIL",
        "results": [
            {"scenario": r.number, "name": r.name, "passed": r.passed, "detail": r.detail}
            for r in results
        ],
    }
