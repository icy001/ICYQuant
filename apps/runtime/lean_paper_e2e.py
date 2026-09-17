"""P0-01 — ICYQuant → LEAN paper track end-to-end validation (8 gates).

Usage:
    python -m apps.runtime lean-paper
    python -m apps.runtime lean-paper --json
    python -m apps.runtime lean-paper --events ~/lean-live.log   # grade Layer B
    python -m apps.runtime lean-paper --gate G03

Artifacts:
    artifacts/lean_paper_e2e/e2e_report.json   8-gate verdicts
    artifacts/lean_paper_e2e/e2e_report.md     human summary
    artifacts/lean_paper_e2e/strategy_contract.json   the payload LEAN reads
    artifacts/lean_paper_e2e/lean_live_command.txt    the deploy argv
    artifacts/lean_paper_e2e/reconciliation.json      G08 detail

The suite runs in two layers, and says which one it is in:

  Layer A (offline, always gradable)
    G01 StrategyContract 创建      G03 ICYQuant → JSON
    G02 Contract validation        G04 LEAN Adapter health

  Layer B (needs the LEAN CLI — a paid QuantConnect organisation)
    G05 LEAN Algorithm 启动        G07 OrderEvent / Fill 返回
    G06 Paper Brokerage 接收订单   G08 ICYQuant Ledger/Reconcile

A Layer B gate that cannot run reports **PENDING**, never PASS: a gate
that did not execute is not a gate that passed.  Layer B becomes gradable
in two ways —

* ``--events PATH`` grades G06/G07/G08 from a real run's events, either
  the JSON ICYQuant recorded or LEAN's own debug log (``.log``/``.txt``),
  which is what an operator actually has in hand after a deployment;
* ``--deploy`` runs ``lean live deploy`` itself, then grades from its
  output.

Without either, Layer B stays PENDING and the exit code is 2, so CI can
tell "not yet run" apart from "ran and failed".
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Optional

from apps.adapters.lean import LeanAdapter, StrategyContract, StrategyIntent
from apps.adapters.lean.contract import CONTRACT_VERSION
from apps.adapters.lean.event_mapper import map_lean_event
from apps.adapters.lean.mapper import contract_to_lean_payload
from apps.adapters.lean.order_mapper import (
    FILL_STATUSES,
    map_order_event,
    order_event_to_ledger_trade,
)

ARTIFACT_DIR = Path("artifacts") / "lean_paper_e2e"
LEAN_PROJECT_DIR = Path("integrations") / "lean" / "paper"

STRATEGY_ID = "ICYQUANT_P0_01"
CONTRACT_FILENAME = "strategy_contract.json"
ALGORITHM_FILE = "main.py"
LEAN_PROJECT_FILE = "lean.json"

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_PENDING = "PENDING"

GATE_NAMES = {
    "G01": "StrategyContract 创建",
    "G02": "Contract validation",
    "G03": "ICYQuant → JSON",
    "G04": "LEAN Adapter health",
    "G05": "LEAN Algorithm 启动",
    "G06": "Paper Brokerage 接收订单",
    "G07": "OrderEvent / Fill 返回",
    "G08": "ICYQuant Ledger/Reconcile",
}

#: G01–G04 are gradable on a laptop with no LEAN installation.
LAYER_A_GATES = ("G01", "G02", "G03", "G04")
LAYER_B_GATES = ("G05", "G06", "G07", "G08")

ACCEPTED_ORDER_STATUSES = frozenset(
    {"NEW", "SUBMITTED", "PARTIALLY_FILLED", "FILLED"}
)

DEBUG_TIMESTAMP = re.compile(r"^(\d{8} \d{2}:\d{2}:\d{2}\.\d{1,3})")


# ══════════════════════════════════════════════════════════════════
# Event ingestion
# ══════════════════════════════════════════════════════════════════
def _parse_kv(segment: str) -> dict[str, str]:
    """Pull ``key=value`` tokens out of one log line."""
    out: dict[str, str] = {}

    for token in segment.split():
        if "=" in token:
            key, _, value = token.partition("=")
            out[key.strip()] = value.strip()

    return out


def _to_signed_int(value: Any) -> int:
    if value in (None, ""):
        return 0

    try:
        return int(Decimal(str(value)))
    except Exception:
        return 0


def _to_price(value: Any) -> Optional[float]:
    if value in (None, "", "0", "0.0"):
        return None

    try:
        parsed = float(value)
    except Exception:
        return None

    return parsed if parsed > 0 else None


def parse_lean_debug_log(text: str) -> list[dict[str, Any]]:
    """Recover order events from LEAN's own debug output.

    This is the operator's realistic input: after a deployment all they
    have is a log file, not a tidy JSON export.
    """
    events: list[dict[str, Any]] = []

    for line in text.splitlines():
        marker = "ICYQUANT_ORDER_EVENT"

        if marker not in line:
            continue

        stamp = DEBUG_TIMESTAMP.match(line.strip())
        fields = _parse_kv(line.split(marker, 1)[1])

        events.append(
            {
                "type": "ORDER_EVENT",
                "order_id": fields.get("order_id", ""),
                "signal_id": fields.get("signal_id", ""),
                "symbol": fields.get("symbol") or None,
                "status": fields.get("status", "UNKNOWN"),
                "quantity": _to_signed_int(fields.get("quantity")),
                "filled_quantity": _to_signed_int(fields.get("fill_qty")),
                "fill_price": _to_price(fields.get("fill_price")),
                "timestamp": stamp.group(1) if stamp else None,
            }
        )

    return events


def load_events(path: Path) -> tuple[list[dict[str, Any]], str]:
    """Load events from a JSON export or a raw LEAN log."""
    text = path.read_text(encoding="utf-8")

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return parse_lean_debug_log(text), "lean-log"

    if isinstance(payload, dict):
        payload = payload.get("events", [])

    if not isinstance(payload, list):
        raise ValueError(f"unsupported events payload in {path}")

    return [event for event in payload if isinstance(event, dict)], "json"


# ══════════════════════════════════════════════════════════════════
# Contract under test
# ══════════════════════════════════════════════════════════════════
def build_contract() -> StrategyContract:
    """The P0-01 contract: one long SPY intent on a paper account."""
    return StrategyContract(
        contract_version=CONTRACT_VERSION,
        strategy_id=STRATEGY_ID,
        mode="paper",
        initial_cash=1_000_000.0,
        symbols=["SPY"],
        intents=[
            StrategyIntent(
                strategy_id=STRATEGY_ID,
                signal_id="p0_buy_spy",
                symbol="SPY",
                side="BUY",
                quantity=100,
                metadata={"source": "p0_e2e"},
            ),
        ],
        metadata={"purpose": "LEAN paper E2E"},
    )


# ══════════════════════════════════════════════════════════════════
# Gate plumbing
# ══════════════════════════════════════════════════════════════════
@dataclass
class GateResult:
    gate: str
    name: str
    status: str
    detail: str
    duration_ms: float = 0.0
    data: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == STATUS_PASS


def _fail_list(problems: list[str]) -> str:
    return "; ".join(problems)


def _dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _normalise_gate(token: str) -> str:
    token = str(token).strip().upper()

    if token.startswith("G") and len(token) == 2:
        token = f"G0{token[1]}"

    return token


class LeanPaperE2E:
    """Runs P0-01 gates G01–G08."""

    def __init__(
        self,
        artifacts_dir: Path,
        repo_root: Path,
        *,
        project_dir: Optional[Path] = None,
        events_path: Optional[Path] = None,
        deploy: bool = False,
        deploy_timeout: int = 900,
    ) -> None:
        self.artifacts = artifacts_dir
        self.repo_root = repo_root
        self.project_dir = (
            Path(project_dir).resolve()
            if project_dir is not None
            else repo_root / LEAN_PROJECT_DIR
        )
        self.adapter = LeanAdapter(self.project_dir)

        self.events_path = events_path
        self.deploy = deploy
        self.deploy_timeout = deploy_timeout

        self.contract = build_contract()
        self.payload: Optional[dict] = None
        self.contract_path: Optional[Path] = None
        self.command: Optional[list[str]] = None
        self.health: Optional[dict] = None
        self.events: Optional[list[dict]] = None
        self.event_source: str = "none"
        self.reconciliation: dict = {}

        self.artifacts.mkdir(parents=True, exist_ok=True)

    # ── event access ───────────────────────────────────────────────
    def load_events_once(self) -> None:
        if self.events_path is None or self.events is not None:
            return

        self.events, self.event_source = load_events(self.events_path)

    def order_events(self) -> list[dict[str, Any]]:
        """Every ingested event, normalised as an order event."""
        return [map_order_event(raw) for raw in (self.events or [])]

    def fills(self) -> list[dict[str, Any]]:
        out = []

        for event in self.order_events():
            if event["status"] not in FILL_STATUSES:
                continue

            if _to_signed_int(event["filled_quantity"]) == 0:
                continue

            if _to_price(event["fill_price"]) is None:
                continue

            out.append(event)

        return out

    # ── G01 ────────────────────────────────────────────────────────
    def g01_contract_created(self) -> GateResult:
        contract = build_contract()
        payload = contract.to_dict()
        problems: list[str] = []

        if payload.get("contract_version") != CONTRACT_VERSION:
            problems.append(
                f"contract_version={payload.get('contract_version')!r}"
            )

        if payload.get("mode") != "paper":
            problems.append(f"mode={payload.get('mode')!r}")

        if payload.get("strategy_id") != STRATEGY_ID:
            problems.append(f"strategy_id={payload.get('strategy_id')!r}")

        if payload.get("symbols") != ["SPY"]:
            problems.append(f"symbols={payload.get('symbols')!r}")

        if len(payload.get("intents", [])) != len(contract.intents):
            problems.append("intent count mismatch after serialisation")

        intent = (payload.get("intents") or [{}])[0]

        for key in ("strategy_id", "signal_id", "symbol", "side", "quantity",
                    "timestamp", "metadata"):
            if key not in intent:
                problems.append(f"intent missing field {key!r}")

        if intent.get("side") != "BUY" or intent.get("quantity") != 100:
            problems.append(
                f"intent={intent.get('side')}/{intent.get('quantity')}"
            )

        try:
            contract.initial_cash = 1.0  # type: ignore[misc]
            problems.append("contract is mutable — it must be frozen")
        except Exception:
            pass

        if problems:
            return GateResult("", "", STATUS_FAIL, _fail_list(problems))

        return GateResult(
            "", "", STATUS_PASS,
            "StrategyContract built, frozen, and serialisable",
            data={"intents": len(contract.intents), "symbols": contract.symbols},
        )

    # ── G02 ────────────────────────────────────────────────────────
    def g02_contract_validation(self) -> GateResult:
        problems: list[str] = []

        good = build_contract()
        good.validate()

        sell = StrategyContract(
            contract_version=CONTRACT_VERSION,
            strategy_id=STRATEGY_ID,
            mode="paper",
            initial_cash=500_000.0,
            symbols=["SPY"],
            intents=[
                StrategyIntent(
                    strategy_id=STRATEGY_ID,
                    signal_id="p0_sell_spy",
                    symbol="SPY",
                    side="SELL",
                    quantity=50,
                    target_weight=-0.1,
                )
            ],
        )
        sell.validate()

        intent = good.intents[0]

        intent_cases = [
            ("unsupported side", replace(intent, side="HOLD")),
            ("zero quantity", replace(intent, quantity=0)),
            ("negative quantity", replace(intent, quantity=-5)),
            ("fractional quantity", replace(intent, quantity=1.5)),
            ("empty symbol", replace(intent, symbol="")),
            ("empty signal_id", replace(intent, signal_id="")),
            ("empty strategy_id", replace(intent, strategy_id="")),
            ("target_weight above 1", replace(intent, target_weight=1.5)),
            ("target_weight below -1", replace(intent, target_weight=-1.5)),
            ("negative limit price", replace(intent, limit_price=-1.0)),
            ("zero stop price", replace(intent, stop_price=0.0)),
        ]

        contract_cases = [
            ("unsupported version", replace(good, contract_version="9.9")),
            ("unsupported mode", replace(good, mode="shadow")),
            ("zero initial cash", replace(good, initial_cash=0.0)),
            ("negative initial cash", replace(good, initial_cash=-1.0)),
            ("no symbols", replace(good, symbols=[])),
            ("duplicate symbols", replace(good, symbols=["SPY", "SPY"])),
            ("empty strategy_id", replace(good, strategy_id="")),
            (
                "intent outside contract symbols",
                replace(good, intents=[replace(intent, symbol="QQQ")]),
            ),
            (
                "intent strategy_id mismatch",
                replace(good, intents=[replace(intent, strategy_id="OTHER")]),
            ),
            (
                "invalid intent inside contract",
                replace(good, intents=[replace(intent, quantity=0)]),
            ),
        ]

        rejected = 0

        for label, bad_intent in intent_cases:
            try:
                bad_intent.validate()
            except ValueError:
                rejected += 1
            else:
                problems.append(f"intent accepted: {label}")

        for label, bad_contract in contract_cases:
            try:
                bad_contract.validate()
            except ValueError:
                rejected += 1
            else:
                problems.append(f"contract accepted: {label}")

        total_cases = len(intent_cases) + len(contract_cases)

        if rejected != total_cases:
            problems.append(f"only {rejected}/{total_cases} invalid inputs rejected")

        if problems:
            return GateResult("", "", STATUS_FAIL, _fail_list(problems))

        return GateResult(
            "", "", STATUS_PASS,
            f"2 valid inputs accepted, {total_cases}/{total_cases} invalid rejected",
            data={"invalid_cases": total_cases, "rejected": rejected},
        )

    # ── G03 ────────────────────────────────────────────────────────
    def g03_icyquant_to_json(self) -> GateResult:
        problems: list[str] = []

        self.contract_path = self.adapter.write_contract(self.contract)
        payload = self.adapter.read_contract()
        self.payload = payload

        expected = contract_to_lean_payload(self.contract)

        if payload != expected:
            problems.append("file content differs from the in-memory payload")

        replay_path = self.project_dir / "strategy_contract.replay.json"
        self.adapter.write_contract(self.contract, filename=replay_path.name)

        try:
            if replay_path.read_text(encoding="utf-8") != self.contract_path.read_text(
                encoding="utf-8"
            ):
                problems.append("serialisation is not deterministic")
        finally:
            replay_path.unlink(missing_ok=True)

        orders = payload.get("orders") or []

        if len(orders) != 1:
            problems.append(f"expected 1 order, found {len(orders)}")
        else:
            order = orders[0]

            if order.get("symbol") != "SPY":
                problems.append(f"order symbol={order.get('symbol')!r}")

            if order.get("side") != "BUY":
                problems.append(f"order side={order.get('side')!r}")

            if order.get("quantity") != 100:
                problems.append(f"order quantity={order.get('quantity')!r}")

            if order.get("signal_id") != "p0_buy_spy":
                problems.append(f"order signal_id={order.get('signal_id')!r}")

        if payload.get("initial_cash") != 1_000_000.0:
            problems.append(f"initial_cash={payload.get('initial_cash')!r}")

        self.payload = payload
        _dump(self.artifacts / CONTRACT_FILENAME, payload)

        command = self.adapter.build_live_command(
            contract_path=self.contract_path,
            output_dir=self.artifacts / "live-results",
        )
        self.command = command
        (self.artifacts / "lean_live_command.txt").write_text(
            " ".join(command), encoding="utf-8"
        )

        if "Paper Trading" not in command:
            problems.append("deploy command does not request Paper Trading")

        if problems:
            return GateResult("", "", STATUS_FAIL, _fail_list(problems))

        return GateResult(
            "", "", STATUS_PASS,
            f"contract written to {self.contract_path.name} "
            f"({self.contract_path.stat().st_size} bytes) and re-read identical",
            data={"path": str(self.contract_path), "orders": len(orders)},
        )

    # ── G04 ────────────────────────────────────────────────────────
    def g04_lean_adapter_health(self) -> GateResult:
        health = self.adapter.health()
        self.health = health
        problems: list[str] = []

        required = {"status", "lean_binary", "docker", "project_dir"}
        missing = required - set(health)

        if missing:
            problems.append(f"health payload missing {sorted(missing)}")

        status = health.get("status")

        if status not in {"OK", "UNAVAILABLE", "ERROR"}:
            problems.append(f"unexpected status {status!r}")

        note = ""

        if status == "UNAVAILABLE":
            if not health.get("detail"):
                problems.append("UNAVAILABLE without a detail message")

            note = (
                "LEAN CLI absent (expected on a fresh Mac) — the adapter still "
                "reports the environment correctly; Layer B stays PENDING"
            )
        elif status == "OK":
            if not health.get("version"):
                problems.append("OK without a version string")

            note = f"LEAN CLI usable ({health.get('version')})"
        elif status == "ERROR":
            problems.append(
                f"LEAN CLI present but unusable: {health.get('detail')}"
            )

        docker = health.get("docker") or {}

        if docker.get("status") not in {"OK", "UNAVAILABLE", "ERROR"}:
            problems.append(f"docker probe returned {docker!r}")

        if problems:
            return GateResult("", "", STATUS_FAIL, _fail_list(problems))

        docker_note = f"docker={docker.get('status')}"

        return GateResult(
            "", "", STATUS_PASS,
            f"{note}; {docker_note}",
            data={
                "status": status,
                "version": health.get("version"),
                "docker": docker.get("status"),
            },
        )

    # ── G05 ────────────────────────────────────────────────────────
    def g05_lean_algorithm_start(self) -> GateResult:
        problems: list[str] = []
        assets: dict[str, Any] = {}

        algorithm = self.project_dir / ALGORITHM_FILE

        if not algorithm.exists():
            problems.append(f"{ALGORITHM_FILE} missing at {algorithm}")
        else:
            source = algorithm.read_text(encoding="utf-8")
            assets["algorithm_bytes"] = len(source)

            try:
                tree = ast.parse(source)
            except SyntaxError as exc:
                problems.append(f"{ALGORITHM_FILE} does not parse: {exc}")
            else:
                classes = {
                    node.name
                    for node in ast.walk(tree)
                    if isinstance(node, ast.ClassDef)
                }
                methods = {
                    node.name
                    for node in ast.walk(tree)
                    if isinstance(node, ast.FunctionDef)
                }

                if "ICYQuantPaperAlgorithm" not in classes:
                    problems.append("algorithm class ICYQuantPaperAlgorithm missing")

                for method in ("Initialize", "OnData", "OnOrderEvent"):
                    if method not in methods:
                        problems.append(f"algorithm hook {method} missing")

                if CONTRACT_FILENAME not in source:
                    problems.append(
                        f"algorithm never references {CONTRACT_FILENAME}"
                    )

        project_file = self.project_dir / LEAN_PROJECT_FILE

        if not project_file.exists():
            problems.append(f"{LEAN_PROJECT_FILE} missing")
        else:
            try:
                project = json.loads(project_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                problems.append(f"{LEAN_PROJECT_FILE} is not valid JSON: {exc}")
            else:
                if project.get("algorithm-language") != "Python":
                    problems.append(
                        f"algorithm-language={project.get('algorithm-language')!r}"
                    )

                assets["algorithm_language"] = project.get("algorithm-language")

        if self.contract_path is None or not Path(self.contract_path).exists():
            # G05 must be gradable on its own (``--gate G05``), so make the
            # suite order-independent by writing the contract now.
            self.g03_icyquant_to_json()

        if self.contract_path is None or not Path(self.contract_path).exists():
            problems.append("strategy contract was not written (G03)")

        if problems:
            return GateResult("", "", STATUS_FAIL, _fail_list(problems))

        if self.health is None:
            self.health = self.adapter.health()

        if self.health.get("status") != "OK":
            return GateResult(
                "", "", STATUS_PENDING,
                "algorithm assets validate offline "
                "(class + hooks + lean.json + contract); starting LEAN needs an "
                "installed CLI and a paid QuantConnect organisation",
                data=assets,
            )

        command = self.command or self.adapter.build_live_command(
            contract_path=self.contract_path,
            output_dir=self.artifacts / "live-results",
        )

        if not self.deploy:
            return GateResult(
                "", "", STATUS_PENDING,
                "LEAN CLI present; re-run with --deploy to start the paper "
                "deployment (long-running)",
                data={**assets, "command": " ".join(command)},
            )

        output = ""
        timed_out = False

        try:
            proc = subprocess.run(
                command,
                cwd=str(self.project_dir.parent),
                capture_output=True,
                text=True,
                timeout=self.deploy_timeout,
                check=False,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            code = proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            output = (exc.stdout or "") + (exc.stderr or "")
            if isinstance(output, bytes):
                output = output.decode("utf-8", "replace")
            code = None
        except Exception as exc:
            return GateResult(
                "", "", STATUS_FAIL, f"deploy could not run: {exc}"
            )

        (self.artifacts / "lean_live_output.txt").write_text(
            output, encoding="utf-8"
        )
        assets["timed_out"] = timed_out
        assets["returncode"] = code

        if "ICYQUANT_CONTRACT" not in output:
            return GateResult(
                "", "", STATUS_FAIL,
                "deploy produced no ICYQUANT_CONTRACT line — the algorithm did "
                "not initialise (see live-results/lean_live_output.txt)",
                data=assets,
            )

        if not timed_out and code not in (0, None):
            return GateResult(
                "", "", STATUS_FAIL,
                f"deploy exited with {code} after initialising",
                data=assets,
            )

        return GateResult(
            "", "", STATUS_PASS,
            "LEAN initialised the algorithm and read the contract"
            + (" (deployment still running when the timeout hit)" if timed_out else ""),
            data=assets,
        )

    # ── G06 ────────────────────────────────────────────────────────
    def g06_paper_brokerage_order(self) -> GateResult:
        self.load_events_once()

        if not self.events:
            return GateResult(
                "", "", STATUS_PENDING,
                "no LEAN events supplied — pass --events <log|json> from a real "
                "paper deployment to grade this gate",
            )

        orders = self.order_events()
        symbols = set(self.contract.symbols)
        problems: list[str] = []

        accepted = [
            order for order in orders if order["status"] in ACCEPTED_ORDER_STATUSES
        ]

        if not accepted:
            problems.append(
                "no accepted order event "
                f"(statuses seen: {sorted({o['status'] for o in orders})})"
            )

        for order in accepted:
            symbol = order.get("symbol")

            if symbol and symbol not in symbols:
                problems.append(f"order for {symbol!r} outside the contract")

        if problems:
            return GateResult("", "", STATUS_FAIL, _fail_list(problems))

        return GateResult(
            "", "", STATUS_PASS,
            f"paper brokerage accepted {len(accepted)} order event(s) "
            f"from {self.event_source} input",
            data={
                "accepted": len(accepted),
                "statuses": sorted({order["status"] for order in accepted}),
                "source": self.event_source,
            },
        )

    # ── G07 ────────────────────────────────────────────────────────
    def g07_order_event_fill(self) -> GateResult:
        self.load_events_once()

        if not self.events:
            return GateResult(
                "", "", STATUS_PENDING,
                "no LEAN events supplied — G07 needs a real fill to grade",
            )

        orders = self.order_events()
        fills = self.fills()
        problems: list[str] = []

        if not fills:
            problems.append(
                "no filled order event "
                f"(statuses seen: {sorted({o['status'] for o in orders})})"
            )

        for fill in fills:
            quantity = _to_signed_int(fill["filled_quantity"])
            price = _to_price(fill["fill_price"])

            if quantity == 0:
                problems.append(f"order {fill['order_id']}: zero fill quantity")

            if price is None:
                problems.append(f"order {fill['order_id']}: no usable fill price")

            envelope = map_lean_event({**fill, "type": "ORDER_EVENT"})

            if envelope["type"] != "EXECUTION":
                problems.append(
                    f"order {fill['order_id']}: event_mapper returned "
                    f"{envelope['type']}"
                )

        if problems:
            return GateResult("", "", STATUS_FAIL, _fail_list(problems))

        return GateResult(
            "", "", STATUS_PASS,
            f"{len(fills)} fill event(s) mapped back to ICYQuant",
            data={
                "fills": len(fills),
                "orders": len({fill["order_id"] for fill in fills}),
                "source": self.event_source,
            },
        )

    # ── G08 ────────────────────────────────────────────────────────
    def g08_ledger_reconcile(self) -> GateResult:
        self.load_events_once()

        if not self.events:
            return GateResult(
                "", "", STATUS_PENDING,
                "no LEAN events supplied — G08 needs a real fill to post and "
                "reconcile",
            )

        fills = self.fills()
        problems: list[str] = []

        if not fills:
            return GateResult(
                "", "", STATUS_FAIL,
                "no fill to post — reconciliation cannot be vacuously true",
            )

        try:
            from services.ledger.posting import PostingEngine
        except Exception as exc:  # pragma: no cover - import environment
            return GateResult(
                "", "", STATUS_FAIL, f"ledger unavailable: {exc}"
            )

        engine = PostingEngine()
        journals: list[dict] = []

        for fill in fills:
            trade = order_event_to_ledger_trade(fill)

            try:
                journal = engine.post_trade(trade)
            except Exception as exc:
                problems.append(f"order {fill['order_id']}: post failed ({exc})")
                continue

            journals.append(
                {
                    "order_id": fill["order_id"],
                    "symbol": trade.symbol,
                    "quantity": str(trade.quantity),
                    "price": str(trade.price),
                    "amount": str(trade.quantity * trade.price),
                    "balanced": journal.is_balanced(),
                }
            )

            if not journal.is_balanced():
                problems.append(f"order {fill['order_id']}: journal unbalanced")

        expected: dict[str, Decimal] = {}
        intents_by_signal = {
            intent.signal_id: intent for intent in self.contract.intents
        }

        fills_by_key: dict[str, Decimal] = {}

        for fill in fills:
            key = fill.get("signal_id") or fill.get("symbol") or ""

            if not key:
                problems.append(f"order {fill['order_id']}: no signal_id/symbol")
                continue

            fills_by_key[key] = fills_by_key.get(key, Decimal("0")) + Decimal(
                _to_signed_int(fill["filled_quantity"])
            )

        matched: list[dict] = []

        for intent in self.contract.intents:
            signed = Decimal(intent.signed_quantity)
            expected[intent.signal_id] = signed

            actual = fills_by_key.pop(intent.signal_id, None)

            if actual is None:
                actual = fills_by_key.pop(intent.symbol, None)

            if actual is None:
                problems.append(
                    f"intent {intent.signal_id}: no fill observed for "
                    f"{intent.symbol} {intent.side} {intent.quantity}"
                )
                continue

            if actual != signed:
                problems.append(
                    f"intent {intent.signal_id}: expected signed quantity "
                    f"{signed}, got {actual}"
                )
                continue

            matched.append(
                {"signal_id": intent.signal_id, "signed_quantity": str(signed)}
            )

        for key, value in fills_by_key.items():
            problems.append(f"unexpected fill for {key!r}: signed {value}")

        self.reconciliation = {
            "commit": "P0-01",
            "event_source": self.event_source,
            "expected": {key: str(value) for key, value in expected.items()},
            "matched": matched,
            "journals": journals,
            "unexpected_fills": {k: str(v) for k, v in fills_by_key.items()},
            "problems": problems,
            "reconciled": not problems,
            "note": (
                "LedgerPostingEngine posts position-vs-cash without a direction; "
                "the sign is verified here, in reconciliation, not in the journal"
            ),
        }
        _dump(self.artifacts / "reconciliation.json", self.reconciliation)

        if problems:
            return GateResult(
                "", "", STATUS_FAIL, _fail_list(problems),
                data={"journals": len(journals), "matched": len(matched)},
            )

        return GateResult(
            "", "", STATUS_PASS,
            f"{len(journals)} fill(s) posted to the ledger and "
            f"{len(matched)} intent(s) reconciled",
            data={
                "journals": len(journals),
                "matched": len(matched),
                "balanced": all(journal["balanced"] for journal in journals),
            },
        )

    # ── driver ─────────────────────────────────────────────────────
    def gate_functions(self) -> list[Callable[[], GateResult]]:
        return [
            self.g01_contract_created,
            self.g02_contract_validation,
            self.g03_icyquant_to_json,
            self.g04_lean_adapter_health,
            self.g05_lean_algorithm_start,
            self.g06_paper_brokerage_order,
            self.g07_order_event_fill,
            self.g08_ledger_reconcile,
        ]

    def run(self, only: Optional[list[str]] = None) -> list[GateResult]:
        wanted = {_normalise_gate(token) for token in only} if only else None
        results: list[GateResult] = []

        for fn in self.gate_functions():
            gate_id = f"G{fn.__name__[1:3]}"

            if wanted and gate_id not in wanted:
                continue

            started = time.perf_counter()

            try:
                result = fn()
            except Exception as exc:
                result = GateResult(
                    "", "", STATUS_FAIL, f"raised {type(exc).__name__}: {exc}"
                )

            result.gate = gate_id
            result.name = GATE_NAMES[gate_id]
            result.duration_ms = round(
                (time.perf_counter() - started) * 1000, 3
            )

            results.append(result)

        return results


# ══════════════════════════════════════════════════════════════════
# Reports
# ══════════════════════════════════════════════════════════════════
def generate_reports(runner: LeanPaperE2E,
                     results: list[GateResult]) -> dict:
    passed = sum(1 for r in results if r.status == STATUS_PASS)
    failed = sum(1 for r in results if r.status == STATUS_FAIL)
    pending = sum(1 for r in results if r.status == STATUS_PENDING)
    total = len(results)

    if failed:
        verdict = "FAIL"
    elif pending:
        verdict = "PARTIAL"
    else:
        verdict = "PASS"

    by_gate = {r.gate: r.status for r in results}

    report = {
        "commit": "P0-01",
        "suite": "lean-paper",
        "gate": verdict,
        "passed": passed,
        "failed": failed,
        "pending": pending,
        "total": total,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "layer_a": {
            gate: by_gate.get(gate) for gate in LAYER_A_GATES if gate in by_gate
        },
        "layer_b": {
            gate: by_gate.get(gate) for gate in LAYER_B_GATES if gate in by_gate
        },
        "environment": runner.health,
        "project_dir": str(runner.project_dir),
        "contract_path": str(runner.contract_path) if runner.contract_path else None,
        "lean_command": " ".join(runner.command) if runner.command else None,
        "gates": [
            {
                "gate": r.gate,
                "name": r.name,
                "status": r.status,
                "passed": r.passed,
                "detail": r.detail,
                "duration_ms": r.duration_ms,
                "data": r.data,
            }
            for r in results
        ],
    }

    if verdict != "PASS":
        report["next_action"] = (
            "Layer B (G05–G08) is gradable once LEAN CLI is available: "
            "pip install lean, run `lean init`, then "
            "`python -m apps.runtime lean-paper --deploy`, or grade an "
            "existing run with `--events <lean log or events.json>`."
        )

    _dump(runner.artifacts / "e2e_report.json", report)
    (runner.artifacts / "e2e_report.md").write_text(
        _render_markdown(report), encoding="utf-8"
    )
    return report


def _render_markdown(report: dict) -> str:
    lines = [
        "# P0-01 — ICYQuant → LEAN Paper E2E",
        "",
        f"- **Gate: {report['gate']}** "
        f"({report['passed']} PASS / {report['failed']} FAIL / "
        f"{report['pending']} PENDING of {report['total']})",
        f"- Generated: `{report['generated_at']}`",
        f"- Project: `{report['project_dir']}`",
    ]

    environment = report.get("environment") or {}

    if environment:
        lines.append(
            f"- Environment: LEAN CLI `{environment.get('status')}`, "
            f"Docker `{(environment.get('docker') or {}).get('status')}`"
        )

    if report.get("lean_command"):
        lines.append(f"- Deploy command: `{report['lean_command']}`")

    lines += ["", "| Gate | Name | Status | Detail |", "|---|---|---|---|"]

    for gate in report["gates"]:
        detail = str(gate["detail"]).replace("|", "\\|")
        lines.append(
            f"| {gate['gate']} | {gate['name']} | {gate['status']} | {detail} |"
        )

    if report.get("next_action"):
        lines += ["", "## Next action", "", report["next_action"]]

    lines += [
        "",
        "> A gate that did not run reports PENDING, not PASS.",
        "",
    ]

    return "\n".join(lines)


def _print_summary(report: dict, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return

    print(
        f"P0-01 LEAN PAPER E2E — GATE: {report['gate']} "
        f"({report['passed']} PASS / {report['failed']} FAIL / "
        f"{report['pending']} PENDING of {report['total']})"
    )

    for gate in report["gates"]:
        print(
            f"  [{gate['status']:<7}] {gate['gate']} {gate['name']} "
            f"({gate['duration_ms']} ms)"
        )

        if gate["status"] != STATUS_PASS:
            print(f"            {gate['detail']}")

    print(f"  artifacts → {ARTIFACT_DIR.as_posix()}/")


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point (``python -m apps.runtime lean-paper``)."""
    parser = argparse.ArgumentParser(
        prog="lean-paper-e2e",
        description="P0-01 — ICYQuant → LEAN paper track E2E validation "
                    "(8 gates; Layer A offline, Layer B needs LEAN CLI).",
    )
    parser.add_argument(
        "--artifacts", default=None,
        help="artifact directory (default: artifacts/lean_paper_e2e)",
    )
    parser.add_argument(
        "--repo-root", default=None, help="repository root override",
    )
    parser.add_argument(
        "--gate", action="append", default=None, metavar="Gnn",
        help="run only the named gate(s), e.g. --gate G03",
    )
    parser.add_argument(
        "--events", default=None, metavar="PATH",
        help="grade Layer B from a real run: LEAN debug log or events JSON",
    )
    parser.add_argument(
        "--deploy", action="store_true",
        help="actually run `lean live deploy` (needs LEAN CLI + organisation)",
    )
    parser.add_argument(
        "--deploy-timeout", type=int, default=900,
        help="seconds to wait for a --deploy run (default: 900)",
    )
    parser.add_argument("--json", action="store_true", help="raw JSON output")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else (
        Path(__file__).resolve().parents[2]
    )
    artifacts = (
        Path(args.artifacts).resolve() if args.artifacts
        else repo_root / ARTIFACT_DIR
    )
    events_path = Path(args.events).expanduser().resolve() if args.events else None

    if events_path is not None and not events_path.exists():
        print(f"events file not found: {events_path}")
        return 2

    runner = LeanPaperE2E(
        artifacts,
        repo_root,
        events_path=events_path,
        deploy=args.deploy,
        deploy_timeout=args.deploy_timeout,
    )
    results = runner.run(only=args.gate)
    report = generate_reports(runner, results)
    _print_summary(report, as_json=args.json)

    if report["failed"]:
        return 1

    if report["pending"]:
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
