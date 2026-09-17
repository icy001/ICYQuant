"""ICYQuant Runtime CLI.

Usage:
    python -m apps.runtime health [--port 8010]      # Health check server (all 10 services)
    python -m apps.runtime scenarios [--json]        # Run Golden Scenarios 01-08
    python -m apps.runtime paper [--signals N]       # Phase 4: paper trading metrics
    python -m apps.runtime shadow [--signals N]      # Commit 016: shadow trading session (real market, simulated fills)
    python -m apps.runtime strategy [--json]         # Phase 7: Strategy 001 backtest (research layer)
    python -m apps.runtime factor [--json]           # Phase 8: Alpha021 factor -> paper trading (research layer)
    python -m apps.runtime e2e --suite market-data   # Commit 017: A-share market data track E2E (20 gates)
    python -m apps.runtime market-data-check         # same suite, short alias
    python -m apps.runtime lean-paper                # P0-01: ICYQuant -> LEAN paper E2E (8 gates)
"""
from __future__ import annotations

import argparse
import json
import sys


def build_parser() -> argparse.ArgumentParser:
    """The single source of truth for the runtime CLI surface.

    Exposed (rather than buried in :func:`main`) so the acceptance
    suite can prove, at the CLI level, that ``shadow --live`` and its
    aliases are rejected before any code runs.
    """
    parser = argparse.ArgumentParser(prog="icyquant-runtime", description="ICYQuant deployment & validation runtime")
    sub = parser.add_subparsers(dest="command", required=True)

    p_health = sub.add_parser("health", help="run health check HTTP server")
    p_health.add_argument("--host", default="0.0.0.0")
    p_health.add_argument("--port", type=int, default=8010)

    p_scen = sub.add_parser("scenarios", help="run Golden Scenarios 01-08")
    p_scen.add_argument("--json", action="store_true", help="output raw JSON")

    p_paper = sub.add_parser("paper", help="Phase 4: paper trading metrics run")
    p_paper.add_argument("--signals", type=int, default=50, help="number of signals to trade")
    p_paper.add_argument("--json", action="store_true", help="output raw JSON")

    p_shadow = sub.add_parser(
        "shadow",
        help="Commit 016: shadow trading session (simulated execution, never a real order)",
        epilog=(
            "Shadow structurally cannot place real orders: it never "
            "accepts --live / --real-order / --broker-order and no code "
            "path reaches a broker order API."
        ),
    )
    p_shadow.add_argument(
        "action",
        nargs="?",
        default="run",
        choices=["run", "status", "stop"],
        help="run the session, or query/stop a running one",
    )
    p_shadow.add_argument("--symbols", default="159852,159559,161116", help="comma-separated symbols to shadow-trade")
    p_shadow.add_argument("--capital", type=float, default=1_000_000, help="shadow initial capital in CNY")
    p_shadow.add_argument("--signals", type=int, default=20, help="max shadow intents per session (0 = unlimited)")
    p_shadow.add_argument("--interval", type=float, default=5.0, help="seconds between session cycles")
    p_shadow.add_argument("--json", action="store_true", help="JSON status lines")

    p_gate = sub.add_parser("gate", help="Phase 6: production readiness gate")
    p_gate.add_argument("--json", action="store_true", help="output raw JSON")

    p_strategy = sub.add_parser("strategy", help="Phase 7: Strategy 001 backtest (research layer)")
    p_strategy.add_argument("--json", action="store_true", help="output raw JSON")

    p_factor = sub.add_parser("factor", help="Phase 8: Alpha021 factor -> paper trading (research layer)")
    p_factor.add_argument("--json", action="store_true", help="output raw JSON")
    p_factor.add_argument("--export", nargs="?", const="__default__", metavar="DIR",
                          help="export the full trade/equity log as CSV "
                               "(default dir: research/discovery/output/factor-paper-d1)")

    def _add_e2e_args(target: argparse.ArgumentParser) -> None:
        target.add_argument(
            "--suite", default="market-data", choices=["market-data"],
            help="validation suite (Commit 017 ships the market-data track)",
        )
        target.add_argument(
            "--artifacts", default=None,
            help="artifact directory (default: artifacts/market_data_e2e)",
        )
        target.add_argument(
            "--gate", action="append", default=None, metavar="Gnn",
            help="run only the named gate(s), e.g. --gate G15",
        )
        target.add_argument("--json", action="store_true", help="raw JSON output")

    p_e2e = sub.add_parser(
        "e2e",
        help="Commit 017: A-share market data track end-to-end validation (20 gates)",
    )
    _add_e2e_args(p_e2e)

    p_mdc = sub.add_parser(
        "market-data-check",
        help="alias for `e2e --suite market-data`",
    )
    _add_e2e_args(p_mdc)

    p_lean = sub.add_parser(
        "lean-paper",
        help="P0-01: ICYQuant -> LEAN paper E2E (8 gates; Layer A offline)",
        epilog=(
            "Layer B (G05-G08) needs the LEAN CLI and a paid QuantConnect "
            "organisation. Until a real deployment's events are supplied via "
            "--events, those gates report PENDING - never PASS."
        ),
    )
    p_lean.add_argument("--artifacts", default=None,
                        help="artifact directory (default: artifacts/lean_paper_e2e)")
    p_lean.add_argument("--repo-root", default=None, help="repository root override")
    p_lean.add_argument("--gate", action="append", default=None, metavar="Gnn",
                        help="run only the named gate(s), e.g. --gate G03")
    p_lean.add_argument("--events", default=None, metavar="PATH",
                        help="grade Layer B from a real run: LEAN debug log or events JSON")
    p_lean.add_argument("--deploy", action="store_true",
                        help="actually run `lean live deploy` (needs LEAN CLI + organisation)")
    p_lean.add_argument("--deploy-timeout", type=int, default=900,
                        help="seconds to wait for a --deploy run (default: 900)")
    p_lean.add_argument("--json", action="store_true", help="output raw JSON")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "health":
        return _run_health(args)
    if args.command == "scenarios":
        return _run_scenarios(args)
    if args.command == "paper":
        return _run_paper(args)
    if args.command == "shadow":
        from apps.runtime.shadow_cli import run_shadow_session, shadow_status, shadow_stop

        if args.action == "status":
            return shadow_status(args)
        if args.action == "stop":
            return shadow_stop(args)
        return run_shadow_session(args)
    if args.command == "gate":
        return _run_gate(args)
    if args.command == "strategy":
        return _run_strategy(args)
    if args.command == "factor":
        return _run_factor(args)
    if args.command in ("e2e", "market-data-check"):
        return _run_market_data_e2e(args)
    if args.command == "lean-paper":
        return _run_lean_paper(args)
    parser.print_help()
    return 2


def _run_lean_paper(args) -> int:
    """P0-01 acceptance suite — Layer A offline, Layer B needs LEAN CLI."""
    from apps.runtime.lean_paper_e2e import main as lean_main

    argv: list[str] = []
    for value in (
        ("--artifacts", getattr(args, "artifacts", None)),
        ("--repo-root", getattr(args, "repo_root", None)),
        ("--events", getattr(args, "events", None)),
    ):
        if value[1]:
            argv += [value[0], value[1]]
    for gate in getattr(args, "gate", None) or []:
        argv += ["--gate", gate]
    if getattr(args, "deploy", False):
        argv.append("--deploy")
    if getattr(args, "deploy_timeout", None) != 900 and getattr(args, "deploy_timeout", None):
        argv += ["--deploy-timeout", str(args.deploy_timeout)]
    if getattr(args, "json", False):
        argv.append("--json")
    return lean_main(argv)


def _run_market_data_e2e(args) -> int:
    """Commit 017 acceptance suite — deterministic, offline, no network."""
    from apps.runtime.e2e_market_data import main as e2e_main

    argv = ["--suite", args.suite]
    if args.artifacts:
        argv += ["--artifacts", args.artifacts]
    if args.gate:
        for gate in args.gate:
            argv += ["--gate", gate]
    if args.json:
        argv.append("--json")
    return e2e_main(argv)


def _run_health(args) -> int:
    import uvicorn

    from apps.runtime.health_server import create_app

    print(f"ICYQuant Health server on http://{args.host}:{args.port}/health")
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="warning")
    return 0


def _run_paper(args) -> int:
    from apps.runtime.paper_trading import (
        PaperAccount,
        PaperTradingSession,
        SignalSpec,
        SimulatedMarketFeed,
    )

    feed = SimulatedMarketFeed(seed=42)
    session = PaperTradingSession(feed=feed, account=PaperAccount(initial_cash=1_000_000.0))
    symbols = ["AAPL", "MSFT", "TSLA"]
    signals = [
        SignalSpec(
            symbol=symbols[i % len(symbols)],
            side="BUY" if i % 3 != 2 else "SELL",
            quantity=100 + (i % 5) * 25,
        )
        for i in range(args.signals)
    ]
    report = session.run(signals)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        m = report["metrics"]
        print(f"PHASE 4 PAPER TRADING - GATE: {'PASS' if m['error_rate_pct'] < 100 else 'FAIL'}")
        print(f"  signals={m['signals']}  fill={m['fill_rate_pct']}%  "
              f"reject={m['reject_rate_pct']}%  error={m['error_rate_pct']}%")
        print(f"  latency(signal/risk/order/total) us avg: {m['latency_signal_us_avg']} / "
              f"{m['latency_risk_us_avg']} / {m['latency_order_us_avg']} / {m['latency_total_us_avg']}")
        print(f"  slippage bps avg: {m['slippage_bps_avg']}  "
              f"equity: {report['equity']}  ledger events: {report['ledger_events']}")
    return 0


def _run_gate(args) -> int:
    from apps.runtime.readiness_gate import run_gate

    result = run_gate()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"PHASE 6 PRODUCTION READINESS GATE: {result['gate']} ({result['passed']}/{result['total']})")
        for cat in result["categories"]:
            mark = "PASS" if cat["all_passed"] else "FAIL"
            print(f"  [{mark}] {cat['name']} ({cat['passed']}/{cat['total']})")
            for item in cat["items"]:
                imark = "PASS" if item["passed"] else "FAIL"
                print(f"      {item['id']} [{imark}] {item['title']}: {item['detail']}")
    return 0 if result["gate"] == "PASS" else 1


def _run_strategy(args) -> int:
    from apps.runtime.strategy_gate import main as strategy_main

    return strategy_main(["--json"] if args.json else [])


def _run_factor(args) -> int:
    from apps.runtime.factor_gate import main as factor_main

    fwd: list[str] = []
    if getattr(args, "json", False):
        fwd.append("--json")
    export = getattr(args, "export", None)
    if export is not None:
        # "__default__" lets factor_gate resolve its own default dir
        fwd += ["--export"] + ([] if export == "__default__" else [export])
    return factor_main(fwd)


def _run_scenarios(args) -> int:
    from apps.runtime.scenarios import run_all_scenarios, summarize

    summary = summarize(run_all_scenarios())
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"GATE: {summary['gate']} ({summary['passed']}/{summary['total']})")
        for r in summary["results"]:
            mark = "PASS" if r["passed"] else "FAIL"
            print(f"  Scenario {r['scenario']:02d} [{mark}] {r['name']}: {r['detail']}")
    return 0 if summary["gate"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
