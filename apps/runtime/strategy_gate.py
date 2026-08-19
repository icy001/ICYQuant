"""Phase 7 - Research Layer: Strategy Gate.

End-to-end verification that the research layer is wired into the
deployed stack for the first production strategy:

    NVDA 15m data (data/lakehouse/NVDA_15m.csv)
        -> Strategy 001 (dual moving-average cross, research.strategy)
        -> BacktestRunner (research.backtest)
        -> PerformanceReport (research.analytics)

Runs on the same container as the API. Data file is synced into
`/app/data/lakehouse` (see VALIDATION_REPORT.md).

Usage:
    python -m apps.runtime strategy
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path

from research.analytics.report import PerformanceReport
from research.backtest.runner import BacktestRunner
from research.data.csv_provider import CsvMarketDataProvider
from research.data.types import TimeFrame
from research.strategy.strategy_001 import STRATEGY_ID, STRATEGY_NAME, Strategy001

GATE_ID = "strategy"
GATE_TITLE = "Strategy Gate - Strategy 001 / NVDA 15m backtest"
SYMBOL = "NVDA"
TIMEFRAME = TimeFrame.M15
START = datetime(2025, 4, 1)
END = datetime(2025, 7, 1)
INITIAL_CAPITAL = 500_000.0


def data_dir() -> Path:
    """Resolve the lakehouse data directory (host or container path)."""
    override = os.getenv("ICYQUANT_DATA_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "data" / "lakehouse"


def run_strategy_gate(initial_capital: float = INITIAL_CAPITAL) -> dict:
    """Run the end-to-end Strategy 001 backtest and return check results."""
    checks: list[dict] = []
    detail_lines: list[str] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        detail_lines.append(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    root = data_dir()
    csv_path = root / f"{SYMBOL}_{TIMEFRAME.value}.csv"
    check("data file present", csv_path.exists(), str(csv_path))
    if not csv_path.exists():
        ok = all(c["ok"] for c in checks)
        return {
            "gate": GATE_ID,
            "ok": ok,
            "checks": checks,
            "detail": "\n".join(detail_lines),
        }

    try:
        provider = CsvMarketDataProvider(root)
        bars = provider.load_bars(
            symbol=SYMBOL,
            timeframe=TIMEFRAME,
            start=START,
            end=END,
        )
    except Exception as exc:  # noqa: BLE001 - gate reports any failure
        check("data load", False, f"{type(exc).__name__}: {exc}")
        return {
            "gate": GATE_ID,
            "ok": False,
            "checks": checks,
            "detail": "\n".join(detail_lines),
        }

    check("data volume", len(bars) >= 1000, f"{len(bars)} bars loaded")
    if len(bars) == 0:
        return {
            "gate": GATE_ID,
            "ok": False,
            "checks": checks,
            "detail": "\n".join(detail_lines),
        }

    try:
        strategy = Strategy001(symbol=SYMBOL)
        runner = BacktestRunner(
            data_provider=provider,
            strategy=strategy,
            symbol=SYMBOL,
            initial_capital=initial_capital,
        )
        report: PerformanceReport = runner.run(
            start=START,
            end=END,
            timeframe=TIMEFRAME,
        )
    except Exception as exc:  # noqa: BLE001
        check("backtest run", False, f"{type(exc).__name__}: {exc}")
        return {
            "gate": GATE_ID,
            "ok": False,
            "checks": checks,
            "detail": "\n".join(detail_lines),
        }

    check(
        "equity curve complete",
        len(report.equity_curve) == len(bars),
        f"{len(report.equity_curve)}/{len(bars)} points",
    )
    check("trades generated", report.num_trades >= 1, f"{report.num_trades} trades")
    check(
        "metrics computed",
        all(
            math.isfinite(v)
            for v in (
                report.total_return,
                report.max_drawdown,
                report.sharpe_ratio,
                report.sortino_ratio,
            )
        ),
        f"return={report.total_return:.2%} dd={report.max_drawdown:.2%} "
        f"sharpe={report.sharpe_ratio:.3f} sortino={report.sortino_ratio:.3f}",
    )
    check(
        "capital positive",
        report.final_equity > 0,
        f"final equity ${report.final_equity:,.0f}",
    )

    ok = all(c["ok"] for c in checks)
    detail_lines.insert(
        0,
        f"Strategy {STRATEGY_ID} ({STRATEGY_NAME}) "
        f"on {SYMBOL} {TIMEFRAME.value}: "
        f"{'PASS' if ok else 'FAIL'}",
    )
    return {
        "gate": GATE_ID,
        "ok": ok,
        "checks": checks,
        "report": {
            "symbol": report.symbol,
            "strategy": report.strategy_name,
            "initial_capital": report.initial_capital,
            "final_equity": report.final_equity,
            "total_return": report.total_return,
            "max_drawdown": report.max_drawdown,
            "sharpe_ratio": report.sharpe_ratio,
            "sortino_ratio": report.sortino_ratio,
            "num_trades": report.num_trades,
            "win_rate": report.win_rate,
            "equity_points": len(report.equity_curve),
        },
        "detail": "\n".join(detail_lines),
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv

    result = run_strategy_gate()

    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["ok"] else 1

    print(f"\n{GATE_TITLE}")
    print(result["detail"])
    print(f"\nSummary: {'ALL CHECKS PASSED' if result['ok'] else 'CHECKS FAILED'}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
