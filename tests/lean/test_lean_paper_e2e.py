"""P0-01 acceptance tests — ICYQuant → LEAN paper track.

Layer A (contract, mappers, adapter, algorithm assets) is asserted
offline.  Layer B is asserted on both of its real behaviours: it grades
from supplied evidence, and it refuses to pass when there is none.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from apps.adapters.lean import (
    CONTRACT_FILENAME,
    LeanAdapter,
    StrategyContract,
    StrategyIntent,
)
from apps.adapters.lean.contract import CONTRACT_VERSION
from apps.adapters.lean.event_mapper import map_lean_event
from apps.adapters.lean.mapper import contract_to_lean_payload, normalize_side
from apps.adapters.lean.order_mapper import (
    map_lean_order_status,
    map_order_event,
    order_event_to_ledger_trade,
)
from apps.adapters.lean.position_mapper import map_lean_position
from apps.runtime.lean_paper_e2e import (
    LAYER_A_GATES,
    LAYER_B_GATES,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_PENDING,
    LeanPaperE2E,
    generate_reports,
    parse_lean_debug_log,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LEAN_PROJECT = REPO_ROOT / "integrations" / "lean" / "paper"

SAMPLE_LOG = """
20260102 09:30:01.501 TRACE:: ICYQUANT_CONTRACT contract_version=1.0 strategy_id=ICYQUANT_P0_01 mode=paper symbols=SPY intents=1
20260102 09:30:02.000 TRACE:: ICYQUANT_ORDER signal_id=p0_buy_spy order_id=1 symbol=SPY side=BUY quantity=100
20260102 09:30:02.410 TRACE:: ICYQUANT_ORDER_EVENT order_id=1 signal_id=p0_buy_spy symbol=SPY status=Submitted quantity=100 fill_qty=0 fill_price=0
20260102 09:30:02.988 TRACE:: ICYQUANT_ORDER_EVENT order_id=1 signal_id=p0_buy_spy symbol=SPY status=Filled quantity=100 fill_qty=100 fill_price=597.42
20260102 09:31:00.000 TRACE:: ICYQUANT_END strategy_id=ICYQUANT_P0_01 orders=1 cash=940258.00 invested=True
""".strip()


# ══════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════
@pytest.fixture()
def lean_project(tmp_path: Path) -> Path:
    """A throwaway copy of the LEAN project, so tests never mutate the repo."""
    project = tmp_path / "paper"
    project.mkdir()

    for name in ("main.py", "lean.json"):
        shutil.copy2(LEAN_PROJECT / name, project / name)

    return project


@pytest.fixture()
def runner(tmp_path: Path, lean_project: Path) -> LeanPaperE2E:
    return LeanPaperE2E(
        tmp_path / "artifacts", REPO_ROOT, project_dir=lean_project
    )


@pytest.fixture()
def events_file(tmp_path: Path) -> Path:
    path = tmp_path / "lean-live.log"
    path.write_text(SAMPLE_LOG, encoding="utf-8")
    return path


# ══════════════════════════════════════════════════════════════════
# G01 / G02 — Contract
# ══════════════════════════════════════════════════════════════════
def test_contract_is_frozen_and_serialisable() -> None:
    contract = StrategyContract(
        contract_version=CONTRACT_VERSION,
        strategy_id="S1",
        mode="paper",
        initial_cash=100_000.0,
        symbols=["SPY"],
        intents=[
            StrategyIntent(
                strategy_id="S1",
                signal_id="sig-1",
                symbol="SPY",
                side="buy",
                quantity=10,
            )
        ],
    )

    contract.validate()
    payload = contract.to_dict()

    assert payload["intents"][0]["quantity"] == 10
    assert payload["symbols"] == ["SPY"]

    with pytest.raises(Exception):
        contract.initial_cash = 1.0  # type: ignore[misc]


@pytest.mark.parametrize(
    "overrides",
    [
        {"side": "HOLD"},
        {"quantity": 0},
        {"quantity": -1},
        {"quantity": 2.5},
        {"symbol": ""},
        {"signal_id": ""},
        {"strategy_id": ""},
        {"target_weight": 1.5},
        {"limit_price": -1.0},
        {"stop_price": 0.0},
    ],
)
def test_intent_validation_rejects(overrides: dict) -> None:
    base = StrategyIntent(
        strategy_id="S1",
        signal_id="sig-1",
        symbol="SPY",
        side="BUY",
        quantity=10,
    )

    with pytest.raises(ValueError):
        replace(base, **overrides).validate()


@pytest.mark.parametrize(
    "overrides",
    [
        {"contract_version": "9.9"},
        {"mode": "shadow"},
        {"initial_cash": 0.0},
        {"symbols": []},
        {"symbols": ["SPY", "SPY"]},
    ],
)
def test_contract_validation_rejects(overrides: dict) -> None:
    base = StrategyContract(
        contract_version=CONTRACT_VERSION,
        strategy_id="S1",
        mode="paper",
        initial_cash=100_000.0,
        symbols=["SPY"],
        intents=[
            StrategyIntent(
                strategy_id="S1",
                signal_id="sig-1",
                symbol="SPY",
                side="BUY",
                quantity=10,
            )
        ],
    )

    with pytest.raises(ValueError):
        replace(base, **overrides).validate()


def test_contract_validation_rejects_foreign_intent() -> None:
    contract = StrategyContract(
        contract_version=CONTRACT_VERSION,
        strategy_id="S1",
        mode="paper",
        initial_cash=100_000.0,
        symbols=["SPY"],
        intents=[
            StrategyIntent(
                strategy_id="S1",
                signal_id="sig-1",
                symbol="QQQ",
                side="BUY",
                quantity=10,
            )
        ],
    )

    with pytest.raises(ValueError, match="not in contract symbols"):
        contract.validate()


def test_signed_quantity_carries_direction() -> None:
    buy = StrategyIntent(
        strategy_id="S1", signal_id="b", symbol="SPY", side="BUY", quantity=10
    )
    sell = StrategyIntent(
        strategy_id="S1", signal_id="s", symbol="SPY", side="SELL", quantity=10
    )

    assert buy.signed_quantity == 10
    assert sell.signed_quantity == -10


# ══════════════════════════════════════════════════════════════════
# Mappers
# ══════════════════════════════════════════════════════════════════
def test_payload_shape_matches_the_algorithm_contract() -> None:
    payload = contract_to_lean_payload(_sample_contract())

    assert payload["mode"] == "paper"
    assert payload["initial_cash"] == 100_000.0
    assert payload["orders"][0]["side"] == "BUY"
    assert payload["orders"][0]["quantity"] == 10
    assert payload["orders"][0]["signal_id"] == "sig-1"
    # the algorithm reads these keys by name
    assert "intents" not in payload
    assert isinstance(payload["orders"], list)


def test_normalize_side_rejects_unknown() -> None:
    assert normalize_side("buy") == "BUY"

    with pytest.raises(ValueError):
        normalize_side("HOLD")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Filled", "FILLED"),
        ("OrderStatus.FILLED", "FILLED"),
        ("Canceled", "CANCELLED"),
        ("Cancelled", "CANCELLED"),
        ("Invalid", "REJECTED"),
        ("SomethingElse", "UNKNOWN"),
    ],
)
def test_order_status_mapping(raw: str, expected: str) -> None:
    assert map_lean_order_status(raw) == expected


def test_position_mapping_reports_side() -> None:
    long = map_lean_position({"symbol": "SPY", "quantity": 100})
    short = map_lean_position({"symbol": "SPY", "quantity": -100})
    flat = map_lean_position({"symbol": "SPY", "quantity": 0})

    assert long["side"] == "LONG"
    assert short["side"] == "SHORT"
    assert flat["side"] == "FLAT"
    assert long["quantity"] == 100.0


def test_event_envelope_types() -> None:
    assert map_lean_event({"type": "FILL"})["type"] == "EXECUTION"
    assert map_lean_event({"type": "POSITION"})["type"] == "POSITION"
    assert map_lean_event({"type": "ERROR"})["type"] == "ERROR"
    assert map_lean_event({"type": "WHATEVER"})["type"] == "UNKNOWN"


def test_fill_becomes_a_ledger_trade() -> None:
    trade = order_event_to_ledger_trade(
        {
            "order_id": "1",
            "symbol": "SPY",
            "status": "Filled",
            "filled_quantity": 100,
            "fill_price": 597.42,
            "timestamp": "20260102 09:30:02.988",
        }
    )

    assert trade.symbol == "SPY"
    assert trade.quantity == Decimal("100")
    assert trade.price == Decimal("597.42")
    assert trade.filled_at == "20260102 09:30:02.988"


@pytest.mark.parametrize(
    "event",
    [
        {"order_id": "1", "symbol": "SPY", "status": "Submitted"},
        {
            "order_id": "1",
            "symbol": "SPY",
            "status": "Filled",
            "filled_quantity": 0,
            "fill_price": 597.42,
        },
        {
            "order_id": "1",
            "symbol": "SPY",
            "status": "Filled",
            "filled_quantity": 100,
            "fill_price": None,
        },
        {"order_id": "1", "status": "Filled", "filled_quantity": 100, "fill_price": 1},
    ],
)
def test_unfilled_events_cannot_be_posted(event: dict) -> None:
    with pytest.raises(ValueError):
        order_event_to_ledger_trade(event)


def test_posting_engine_accepts_the_mapped_trade() -> None:
    from services.ledger.posting import PostingEngine

    trade = order_event_to_ledger_trade(
        {
            "order_id": "1",
            "symbol": "SPY",
            "status": "Filled",
            "filled_quantity": 100,
            "fill_price": 597.42,
        }
    )

    journal = PostingEngine().post_trade(trade)

    assert journal.is_balanced()


# ══════════════════════════════════════════════════════════════════
# Adapter
# ══════════════════════════════════════════════════════════════════
def test_adapter_round_trips_the_contract(tmp_path: Path) -> None:
    project = tmp_path / "project"
    adapter = LeanAdapter(project)
    contract = _sample_contract()

    path = adapter.write_contract(contract)

    assert path.name == CONTRACT_FILENAME
    assert adapter.read_contract() == contract_to_lean_payload(contract)


def test_adapter_refuses_an_invalid_contract(tmp_path: Path) -> None:
    adapter = LeanAdapter(tmp_path / "project")
    broken = replace(_sample_contract(), mode="shadow")

    with pytest.raises(ValueError):
        adapter.write_contract(broken)


def test_health_reports_the_environment(tmp_path: Path) -> None:
    health = LeanAdapter(tmp_path / "project").health()

    assert health["status"] in {"OK", "UNAVAILABLE", "ERROR"}
    assert health["docker"]["status"] in {"OK", "UNAVAILABLE", "ERROR"}
    assert health["project_dir"] == str((tmp_path / "project").resolve())


def test_live_command_uses_paper_trading(tmp_path: Path) -> None:
    adapter = LeanAdapter(tmp_path / "project")

    command = adapter.build_live_command(
        contract_path=tmp_path / "project" / CONTRACT_FILENAME,
        output_dir=tmp_path / "results",
    )

    assert command[:4] == ["lean", "live", "deploy", str(adapter.project_dir)]
    assert "Paper Trading" in command
    assert str(tmp_path / "results") in command


def test_deploy_paper_refuses_live_mode(tmp_path: Path) -> None:
    adapter = LeanAdapter(tmp_path / "project")
    live = replace(_sample_contract(), mode="live")

    with pytest.raises(ValueError):
        adapter.deploy_paper(live)


# ══════════════════════════════════════════════════════════════════
# Event ingestion
# ══════════════════════════════════════════════════════════════════
def test_lean_debug_log_is_parsed() -> None:
    events = parse_lean_debug_log(SAMPLE_LOG)

    # two order events: an unfilled submission, then the fill
    assert len(events) == 2

    filled = [e for e in events if e["status"] == "Filled"]

    assert len(filled) == 1
    assert filled[0]["symbol"] == "SPY"
    assert filled[0]["filled_quantity"] == 100
    assert filled[0]["fill_price"] == 597.42
    assert filled[0]["signal_id"] == "p0_buy_spy"
    assert map_order_event(filled[0])["status"] == "FILLED"


def test_log_parser_ignores_unrelated_lines() -> None:
    assert parse_lean_debug_log("hello\nworld\n") == []


# ══════════════════════════════════════════════════════════════════
# Gates — Layer A
# ══════════════════════════════════════════════════════════════════
def test_layer_a_gates_pass_offline(runner: LeanPaperE2E) -> None:
    results = runner.run(only=list(LAYER_A_GATES))
    statuses = {r.gate: r.status for r in results}

    assert statuses == {gate: STATUS_PASS for gate in LAYER_A_GATES}


def test_g03_writes_both_the_project_file_and_the_artifact(
    runner: LeanPaperE2E,
) -> None:
    runner.run(only=["G03"])

    project_copy = runner.project_dir / CONTRACT_FILENAME
    artifact_copy = runner.artifacts / CONTRACT_FILENAME

    assert project_copy.exists()
    assert artifact_copy.exists()
    assert json.loads(project_copy.read_text("utf-8")) == json.loads(
        artifact_copy.read_text("utf-8")
    )


def test_algorithm_assets_are_checked_without_lean(runner: LeanPaperE2E) -> None:
    result = runner.run(only=["G05"])[0]

    # Without the CLI the gate must not claim the algorithm started.
    assert result.status == STATUS_PENDING
    assert "offline" in result.detail


def test_missing_algorithm_asset_fails_offline(
    tmp_path: Path, lean_project: Path
) -> None:
    (lean_project / "main.py").unlink()

    runner = LeanPaperE2E(
        tmp_path / "artifacts", REPO_ROOT, project_dir=lean_project
    )
    result = runner.run(only=["G05"])[0]

    assert result.status == STATUS_FAIL


# ══════════════════════════════════════════════════════════════════
# Gates — Layer B
# ══════════════════════════════════════════════════════════════════
def test_layer_b_is_pending_without_evidence(runner: LeanPaperE2E) -> None:
    """A gate that did not run must never be reported as a pass."""
    results = runner.run(only=list(LAYER_B_GATES))

    assert {r.status for r in results} == {STATUS_PENDING}


def test_layer_b_grades_from_a_supplied_log(
    tmp_path: Path, lean_project: Path, events_file: Path
) -> None:
    runner = LeanPaperE2E(
        tmp_path / "artifacts",
        REPO_ROOT,
        project_dir=lean_project,
        events_path=events_file,
    )
    results = {r.gate: r for r in runner.run(only=["G06", "G07", "G08"])}

    assert results["G06"].status == STATUS_PASS
    assert results["G07"].status == STATUS_PASS
    assert results["G08"].status == STATUS_PASS
    assert results["G08"].data["balanced"] is True
    assert results["G08"].data["matched"] == 1

    reconciliation = json.loads(
        (runner.artifacts / "reconciliation.json").read_text("utf-8")
    )
    assert reconciliation["reconciled"] is True
    assert reconciliation["expected"] == {"p0_buy_spy": "100"}


def test_reconciliation_fails_on_a_quantity_mismatch(
    tmp_path: Path, lean_project: Path
) -> None:
    path = tmp_path / "bad.log"
    path.write_text(
        SAMPLE_LOG.replace(
            "fill_qty=100 fill_price=597.42", "fill_qty=50 fill_price=597.42"
        ),
        encoding="utf-8",
    )

    runner = LeanPaperE2E(
        tmp_path / "artifacts",
        REPO_ROOT,
        project_dir=lean_project,
        events_path=path,
    )
    result = runner.run(only=["G08"])[0]

    assert result.status == STATUS_FAIL
    assert "expected signed quantity" in result.detail


def test_events_json_is_accepted(tmp_path: Path, lean_project: Path) -> None:
    path = tmp_path / "events.json"
    path.write_text(
        json.dumps(
            [
                {
                    "order_id": "7",
                    "signal_id": "p0_buy_spy",
                    "symbol": "SPY",
                    "status": "FILLED",
                    "filled_quantity": 100,
                    "fill_price": 597.42,
                }
            ]
        ),
        encoding="utf-8",
    )

    runner = LeanPaperE2E(
        tmp_path / "artifacts",
        REPO_ROOT,
        project_dir=lean_project,
        events_path=path,
    )

    assert runner.run(only=["G06", "G07", "G08"])[0].status == STATUS_PASS


# ══════════════════════════════════════════════════════════════════
# Report
# ══════════════════════════════════════════════════════════════════
def test_report_separates_the_two_layers(runner: LeanPaperE2E) -> None:
    results = runner.run()
    report = generate_reports(runner, results)

    assert report["total"] == 8
    assert set(report["layer_a"]) == set(LAYER_A_GATES)
    assert set(report["layer_b"]) == set(LAYER_B_GATES)
    assert report["gate"] in {"PASS", "PARTIAL", "FAIL"}

    # Layer A is gradable here; Layer B is not, and the verdict says so.
    assert {status for status in report["layer_a"].values()} == {STATUS_PASS}
    assert report["gate"] == "PARTIAL"
    assert report["failed"] == 0

    assert (runner.artifacts / "e2e_report.json").exists()
    assert (runner.artifacts / "e2e_report.md").exists()


def test_report_markdown_marks_pending_gates(runner: LeanPaperE2E) -> None:
    report = generate_reports(runner, runner.run())

    markdown = (runner.artifacts / "e2e_report.md").read_text("utf-8")

    assert "PENDING" in markdown
    assert "PENDING, not PASS" in markdown
    assert report["next_action"]


def _sample_contract() -> StrategyContract:
    return StrategyContract(
        contract_version=CONTRACT_VERSION,
        strategy_id="S1",
        mode="paper",
        initial_cash=100_000.0,
        symbols=["SPY"],
        intents=[
            StrategyIntent(
                strategy_id="S1",
                signal_id="sig-1",
                symbol="SPY",
                side="BUY",
                quantity=10,
            )
        ],
    )
