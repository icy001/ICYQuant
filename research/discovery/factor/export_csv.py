"""Export a Factor Discovery experiment (report.json) to flat CSV files
for offline analysis.

Writes, under ``<report_dir>/csv/`` (or ``--output-dir``):

- ``pairs_gate_passed.csv``
    Every (alpha, asset) pair that passed the 16-item Factor Gate, with
    full train / validation / OOS metrics, walk-forward / stability, costs
    and the pair's rank & score.  ``is_final_candidate_alpha`` marks the
    pairs belonging to the final alphas (>= 3 assets passed).
- ``pairs_all.csv``
    All backtested pairs including rejects: same metric columns plus the
    first failing check (``fail_reason``) and one boolean column per gate
    check (``check_dataset_gate`` ... ``check_slippage``) so rejections can
    be pivoted offline.
- ``alpha_ranking.csv``
    Alpha-level cross-asset summary (the "② Alpha Ranking" table).
- ``convergence.csv``
    Strategy x Factor candidate combinations (the "④" table).

Examples
--------
    python -m research.discovery.factor.export_csv \
        --report research/discovery/output/factor-v1/report.json

    python -m research.discovery.factor.export_csv \
        --report research/discovery/output/factor-v1/report.json \
        --output-dir ~/Desktop/factor-v1-csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

from .factor_gate import FactorGate

_NUM = r"(-?\d+(?:\.\d+)?)"


def _num(pattern: str, text: str) -> Optional[float]:
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None


def _pct(pattern: str, text: str) -> Optional[float]:
    """Parse ``254.31%``-style values into fractions."""
    m = re.search(pattern, text)
    return float(m.group(1)) / 100.0 if m else None


def _details(outcome: dict[str, Any]) -> dict[str, str]:
    return {c["name"]: c.get("detail", "")
            for c in outcome.get("checks", [])}


def _flatten_pair(alpha_id: str, asset: str, outcome: dict[str, Any],
                  score: Optional[float], rank: Optional[int],
                  is_final: bool) -> dict[str, Any]:
    """One row: gate outcome + parsed check details + OOS metrics."""
    d = _details(outcome)
    oos = outcome.get("oos_metrics") or {}

    wf = re.search(r"wf windows positive=(\d+)/(\d+)", d.get("walk_forward", ""))
    wf_pos = int(wf.group(1)) if wf else None
    wf_total = int(wf.group(2)) if wf else None

    row: dict[str, Any] = {
        "alpha_id": alpha_id,
        "asset": asset,
        "passed": outcome.get("passed", False),
        "fail_reason": outcome.get("fail_reason", ""),
        "is_final_candidate_alpha": is_final,
        "rank": rank,
        "score": score,
        # factor computability
        "coverage": _num(r"coverage=" + _NUM, d.get("factor_computable", "")),
        "train_blocks": _num(r"train blocks=" + _NUM,
                             d.get("factor_computable", "")),
        # train segment
        "train_ic": _num(r"train IC=" + _NUM, d.get("train_ic", "")),
        "train_rank_ic": _num(r"train RankIC=" + _NUM,
                              d.get("train_rank_ic", "")),
        "train_icir": _num(r"train ICIR=" + _NUM, d.get("train_icir", "")),
        "train_sharpe": _num(r"train LS sharpe=" + _NUM,
                             d.get("train_performance", "")),
        # validation segment
        "val_ic": _num(r"val IC=" + _NUM, d.get("validation_performance", "")),
        "val_return": _pct(r"val LS return=" + _NUM + "%",
                           d.get("validation_performance", "")),
        # OOS segment (authoritative numbers from oos_metrics)
        "oos_ic": oos.get("ic"),
        "oos_rank_ic": oos.get("rank_ic"),
        "oos_icir": oos.get("icir"),
        "oos_sharpe": oos.get("sharpe"),
        "oos_return": oos.get("total_return"),
        "oos_max_dd": oos.get("max_drawdown"),
        "oos_turnover_per_bar": oos.get("turnover_per_bar"),
        "oos_trade_count": oos.get("trade_count"),
        "oos_blocks": oos.get("blocks"),
        # robustness
        "wf_positive": wf_pos,
        "wf_total": wf_total,
        "wf_frac": _num(r"\(frac=" + _NUM + r"\)",
                        d.get("walk_forward", "")),
        "stability_frac": _num(r"quarter sign consistency=" + _NUM,
                               d.get("stability", "")),
        # costs
        "one_way_bps": _num(r"one-way cost=" + _NUM + r" bps",
                            d.get("transaction_cost", "")),
        "slippage_bps": _num(r"slippage=" + _NUM + r" bps",
                             d.get("slippage", "")),
    }
    # one boolean column per gate check (for pivoting rejections)
    checks = {c["name"]: c.get("passed", False)
              for c in outcome.get("checks", [])}
    for name in FactorGate.CHECK_NAMES:
        row[f"check_{name}"] = checks.get(name)
    return row


PAIR_COLUMNS = [
    "alpha_id", "asset", "passed", "fail_reason", "is_final_candidate_alpha",
    "rank", "score",
    "coverage", "train_blocks",
    "train_ic", "train_rank_ic", "train_icir", "train_sharpe",
    "val_ic", "val_return",
    "oos_ic", "oos_rank_ic", "oos_icir", "oos_sharpe", "oos_return",
    "oos_max_dd", "oos_turnover_per_bar", "oos_trade_count", "oos_blocks",
    "wf_positive", "wf_total", "wf_frac", "stability_frac",
    "one_way_bps", "slippage_bps",
] + [f"check_{n}" for n in FactorGate.CHECK_NAMES]

ALPHA_COLUMNS = [
    "rank", "alpha_id", "status", "assets_passed_count", "assets_passed",
    "breadth", "mean_oos_ic", "mean_oos_rank_ic", "mean_oos_icir",
    "mean_oos_sharpe", "mean_turnover", "score",
]

CONVERGENCE_COLUMNS = [
    "label", "strategy_id", "strategy_structure", "strategy_params",
    "alpha_id", "shared_assets", "strategy_score", "alpha_score",
    "combined_score", "status", "next_step",
]


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> int:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)


def export(report_path: Path, output_dir: Path) -> dict[str, int]:
    """Export one factor experiment report to CSV. Returns row counts."""
    data = json.loads(report_path.read_text(encoding="utf-8"))

    # final alphas = status CANDIDATE in the alpha ranking (>= 3 assets)
    final_alphas = {a["alpha_id"] for a in data.get("alpha_ranking", [])
                    if a.get("status") == "CANDIDATE"}

    # (alpha, asset) -> rank/score from the pair ranking
    pair_scores: dict[tuple[str, str], dict[str, Any]] = {
        (p["alpha_id"], p["asset"]): p
        for p in data.get("pair_ranking", [])
    }

    all_rows: list[dict[str, Any]] = []
    passed_rows: list[dict[str, Any]] = []
    for alpha_id, assets in data.get("outcomes", {}).items():
        for asset, outcome in assets.items():
            pr = pair_scores.get((alpha_id, asset), {})
            row = _flatten_pair(alpha_id, asset, outcome,
                                score=pr.get("score"), rank=pr.get("rank"),
                                is_final=alpha_id in final_alphas)
            all_rows.append(row)
            if outcome.get("passed"):
                passed_rows.append(row)

    alpha_rows = []
    for a in data.get("alpha_ranking", []):
        alpha_rows.append({
            "rank": a.get("rank"),
            "alpha_id": a.get("alpha_id"),
            "status": a.get("status"),
            "assets_passed_count": a.get("assets_passed_count"),
            "assets_passed": "|".join(a.get("assets_passed", [])),
            "breadth": a.get("breadth"),
            "mean_oos_ic": a.get("mean_oos_ic"),
            "mean_oos_rank_ic": a.get("mean_oos_rank_ic"),
            "mean_oos_icir": a.get("mean_oos_icir"),
            "mean_oos_sharpe": a.get("mean_oos_sharpe"),
            "mean_turnover": a.get("mean_turnover"),
            "score": a.get("score"),
        })

    conv_rows = []
    for c in data.get("convergence", {}).get("combinations", []):
        params = c.get("strategy_params")
        conv_rows.append({
            "label": c.get("label"),
            "strategy_id": c.get("strategy_id"),
            "strategy_structure": c.get("strategy_structure"),
            "strategy_params": json.dumps(params, sort_keys=True)
                                if params is not None else "",
            "alpha_id": c.get("alpha_id"),
            "shared_assets": "|".join(c.get("shared_assets", [])),
            "strategy_score": c.get("strategy_score"),
            "alpha_score": c.get("alpha_score"),
            "combined_score": c.get("combined_score"),
            "status": c.get("status"),
            "next_step": c.get("next_step"),
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    counts = {
        "pairs_all": _write_csv(output_dir / "pairs_all.csv",
                                PAIR_COLUMNS, all_rows),
        "pairs_gate_passed": _write_csv(output_dir / "pairs_gate_passed.csv",
                                        PAIR_COLUMNS, passed_rows),
        "alpha_ranking": _write_csv(output_dir / "alpha_ranking.csv",
                                    ALPHA_COLUMNS, alpha_rows),
        "convergence": _write_csv(output_dir / "convergence.csv",
                                  CONVERGENCE_COLUMNS, conv_rows),
    }
    return counts


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m research.discovery.factor.export_csv",
        description="Export a Factor Discovery report.json to flat CSVs "
                    "for offline analysis.",
    )
    parser.add_argument("--report", type=Path, required=True,
                        help="Path to the factor report.json.")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="CSV output directory "
                             "(default: <report_dir>/csv).")
    args = parser.parse_args(argv)

    if not args.report.exists():
        print(f"[export] report not found: {args.report}", file=sys.stderr)
        return 1

    out_dir = args.output_dir or args.report.parent / "csv"
    counts = export(args.report, out_dir)

    print(f"[export] report:  {args.report}")
    print(f"[export] output:  {out_dir}")
    for name, n in counts.items():
        print(f"[export] {name:20s} {n:5d} rows -> {name}.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
