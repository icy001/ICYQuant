"""ICYQuant Runtime CLI.

Usage:
    python -m apps.runtime health [--port 8010]      # Health check server (all 10 services)
    python -m apps.runtime scenarios [--json]        # Run Golden Scenarios 01-08
    python -m apps.runtime paper [--signals N]       # Phase 4: paper trading metrics
    python -m apps.runtime shadow [--signals N]      # Commit 016: shadow trading session (real market, simulated fills)
    python -m apps.runtime strategy [--json]         # Phase 7: Strategy 001 backtest (research layer)
    python -m apps.runtime factor [--json]           # Phase 8: Alpha021 factor -> paper trading (research layer)
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
    parser.print_help()
    return 2


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
