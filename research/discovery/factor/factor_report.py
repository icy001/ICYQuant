"""Factor Discovery Report — the Alpha101 track's four-table output.

Produces a JSON snapshot and a Markdown report with the tables agreed for
Discovery Lab v1:

    ② Alpha Ranking             — every alpha ranked by the sealed alpha score
    ③ Cross-Asset Alpha Matrix  — 101 x 9 matrix of OOS ICIR (+ pass flags)
       (plus a pair-level ranking of gate-passing (alpha, asset) pairs)
    ④ Strategy x Factor Candidates
                                — convergence with the Strategy Discovery
                                  line: surviving strategies x surviving
                                  factors -> combined Paper-Trading candidates

Table ① (Strategy Ranking) lives in the strategy line's report; the
convergence table references it by experiment id.

The alpha-level score uses the sealed ``ALPHA_SCORE_WEIGHTS`` for ranking and
reporting **only** — it never relaxes or re-orders the gate.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .factor_engine import FactorExperimentResult
from .factor_spec import ALPHA_SCORE_WEIGHTS, FACTOR_SPEC_V1

TOP_ALPHAS_IN_MD = 25        # rows of table ② rendered in Markdown
TOP_PAIRS_IN_MD = 30         # rows of the pair ranking rendered in Markdown
MAX_CONVERGENCE_COMBOS = 15  # rows of table ④
DEFAULT_STRATEGY_REPORT = "lab-v1"


class FactorReport:
    """Builds and persists the JSON + Markdown report for a factor experiment."""

    def __init__(self, output_dir: Optional[Path] = None,
                 spec=None) -> None:
        self.output_dir = output_dir or (
            Path(__file__).resolve().parents[1] / "output")
        self.spec = spec or FACTOR_SPEC_V1

    # ------------------------------------------------------------------ #
    def build(self, result: FactorExperimentResult,
              strategy_report_path: Optional[Path] = None) -> dict[str, Any]:
        """Assemble the full report dict (JSON-serialisable)."""
        data = result.to_dict()
        data["report_generated_at"] = datetime.now(timezone.utc).isoformat()

        data["alpha_ranking"] = self._alpha_ranking(result)
        data["pair_ranking"] = result.ranked_pairs
        data["cross_asset_matrix"] = result.cross_asset_matrix

        strategy = self._load_strategy_report(strategy_report_path)
        data["strategy_experiment_id"] = (
            strategy.get("experiment_id") if strategy else None)
        data["convergence"] = self._convergence(result, strategy)
        return data

    # ------------------------------------------------------------------ #
    def _alpha_ranking(self, result: FactorExperimentResult
                       ) -> list[dict[str, Any]]:
        """Table ② — rank all alphas with the sealed alpha-level score."""
        universe = list(result.cross_asset_matrix.get("assets", []))
        n_assets = len(universe) or 1
        rows: list[dict[str, Any]] = []
        for alpha_id, per_asset in result.outcomes.items():
            oms = [od["oos_metrics"] for od in per_asset.values()]
            ics = [m["ic"] for m in oms if m.get("ic") is not None]
            rics = [m["rank_ic"] for m in oms if m.get("rank_ic") is not None]
            icirs = [m["icir"] for m in oms if m.get("icir") is not None]
            sharpes = [m.get("sharpe", 0.0) for m in oms]
            tos = [m.get("turnover_per_bar", 0.0) for m in oms]
            n_passed = sum(1 for od in per_asset.values() if od["passed"])
            rows.append({
                "alpha_id": alpha_id,
                "assets_passed_count": n_passed,
                "assets_passed": [a for a, od in per_asset.items()
                                  if od["passed"]],
                "breadth": n_passed / n_assets,
                "mean_oos_ic": _mean(ics),
                "mean_oos_rank_ic": _mean(rics),
                "mean_oos_icir": _mean(icirs),
                "mean_oos_sharpe": _mean([s for s in sharpes]) or 0.0,
                "mean_turnover": _mean(tos) or 0.0,
                "status": "CANDIDATE" if n_passed >=
                self.spec.thresholds["min_assets_passed"] else "REJECTED",
            })

        w = ALPHA_SCORE_WEIGHTS

        def _norm(vals: list[float], lo: float, hi: float) -> list[float]:
            xs = [min(hi, max(lo, v)) for v in vals]
            if not xs:
                return []
            mn, mx = min(xs), max(xs)
            if mx <= mn:
                return [0.5] * len(xs)
            return [(x - mn) / (mx - mn) for x in xs]

        icir_n = _norm([abs(r["mean_oos_icir"] or 0.0) for r in rows], 0.0, 3.0)
        sharpe_n = _norm([r["mean_oos_sharpe"] for r in rows], 0.0, 5.0)
        ic_n = _norm([abs(r["mean_oos_ic"] or 0.0) for r in rows], 0.0, 0.2)
        breadth_n = _norm([r["breadth"] for r in rows], 0.0, 1.0)
        for i, r in enumerate(rows):
            r["score"] = round(
                w["oos_icir"] * icir_n[i]
                + w["oos_sharpe"] * sharpe_n[i]
                + w["oos_ic"] * ic_n[i]
                + w["breadth"] * breadth_n[i], 4)
        rows.sort(key=lambda r: (-r["score"], r["alpha_id"]))
        for i, r in enumerate(rows, 1):
            r["rank"] = i
        return rows

    # ------------------------------------------------------------------ #
    @staticmethod
    def _load_strategy_report(path: Optional[Path]) -> Optional[dict[str, Any]]:
        if path is None:
            default = (Path(__file__).resolve().parents[1] / "output"
                       / DEFAULT_STRATEGY_REPORT / "report.json")
            path = default
        path = Path(path)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    # ------------------------------------------------------------------ #
    def _convergence(self, result: FactorExperimentResult,
                     strategy: Optional[dict[str, Any]]) -> dict[str, Any]:
        """Table ④ — Strategy x Factor combined Paper-Trading candidates.

        Both sides must have survived their own gates for a combination to be
        flagged CANDIDATE; otherwise rows are marked PROVISIONAL (watch list,
        not promoted).
        """
        alpha_rows = self._alpha_ranking(result)
        alpha_candidates = [r for r in alpha_rows if r["status"] == "CANDIDATE"]
        # watch list: top alphas by |mean OOS ICIR| even if they failed breadth
        watch = sorted(
            alpha_rows,
            key=lambda r: -(abs(r["mean_oos_icir"])
                            if r["mean_oos_icir"] is not None else 0.0))[:5]

        strategies: list[dict[str, Any]] = []
        if strategy:
            for s in strategy.get("top_candidates_detail", []):
                strategies.append({
                    "candidate_id": s["candidate_id"],
                    "family": s.get("family", ""),
                    "structure_id": s.get("structure_id", ""),
                    "params": s.get("params", {}),
                    "assets": list(s.get("assets", [])),
                    "total_score": s.get("total_score", 0.0),
                })

        # assets of interest per factor: gate-passed assets for CANDIDATEs;
        # for watch-list factors the top-3 assets by |OOS ICIR|
        matrix = result.cross_asset_matrix.get("icir", {})
        watch_assets: dict[str, list[str]] = {}
        for f in watch:
            per_asset = matrix.get(f["alpha_id"], {})
            ranked = sorted(
                ((a, abs(v)) for a, v in per_asset.items() if v is not None),
                key=lambda kv: -kv[1])
            watch_assets[f["alpha_id"]] = [a for a, _ in ranked[:3]]

        combos: list[dict[str, Any]] = []
        if strategies and (alpha_candidates or watch):
            s_scores = [s["total_score"] for s in strategies] or [0.0]
            s_lo, s_hi = min(s_scores), max(s_scores)

            factors = alpha_candidates if alpha_candidates else watch
            f_status = "CANDIDATE" if alpha_candidates else "PROVISIONAL"
            f_scores = [abs(f["mean_oos_icir"] or 0.0) for f in factors]
            f_lo, f_hi = (min(f_scores), max(f_scores)) if f_scores else (0, 1)

            for s in strategies:
                s_n = _norm1(s["total_score"], s_lo, s_hi)
                for f in factors:
                    if f["status"] == "CANDIDATE":
                        f_assets = f["assets_passed"]
                    else:
                        f_assets = watch_assets.get(f["alpha_id"], [])
                    shared = sorted(set(s["assets"]) & set(f_assets))
                    if not shared:
                        continue
                    f_n = _norm1(abs(f["mean_oos_icir"] or 0.0), f_lo, f_hi)
                    combos.append({
                        "label": f"{s['structure_id']} + {f['alpha_id']}",
                        "strategy_id": s["candidate_id"],
                        "strategy_structure": s["structure_id"],
                        "strategy_params": s["params"],
                        "alpha_id": f["alpha_id"],
                        "shared_assets": shared,
                        "strategy_score": round(s["total_score"], 4),
                        "alpha_score": f["score"],
                        "combined_score": round(0.5 * s_n + 0.5 * f_n, 4),
                        "status": f_status,
                        "next_step": "PAPER_TRADING" if f_status == "CANDIDATE"
                        else "WATCH_LIST",
                    })
            combos.sort(key=lambda c: (-c["combined_score"],
                                       c["label"]))
            combos = combos[:MAX_CONVERGENCE_COMBOS]

        return {
            "strategy_report_found": bool(strategy),
            "strategy_experiment_id": (strategy or {}).get("experiment_id"),
            "strategy_final_candidates": (strategy or {}).get(
                "funnel", {}).get("final_candidates", 0),
            "factor_candidates": [r["alpha_id"] for r in alpha_candidates],
            "factor_watch_list": [r["alpha_id"] for r in watch
                                  if r["alpha_id"] not in
                                  {c["alpha_id"] for c in alpha_candidates}],
            "watch_list_assets": watch_assets,
            "combinations": combos,
        }

    # ------------------------------------------------------------------ #
    def save(self, data: dict[str, Any], experiment_id: str) -> tuple[Path, Path]:
        """Write report.json and report.md under output/<experiment_id>/."""
        out_dir = self.output_dir / experiment_id
        out_dir.mkdir(parents=True, exist_ok=True)
        json_path = out_dir / "report.json"
        json_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        md_path = out_dir / "report.md"
        md_path.write_text(self.to_markdown(data), encoding="utf-8")
        return json_path, md_path

    # ------------------------------------------------------------------ #
    def to_markdown(self, data: dict[str, Any]) -> str:
        funnel = data.get("funnel", {})
        split = data.get("split", {})
        lines: list[str] = []
        w = lines.append
        w("# ICYQuant — Factor Discovery Track (Alpha101) Report")
        w("")
        w(f"- **Experiment**: `{data['experiment_id']}`")
        w(f"- **Spec version**: `{data.get('spec', {}).get('version', '')}`")
        w(f"- **Generated at**: `{data.get('report_generated_at', '')}`")
        w(f"- **Runtime**: {data.get('runtime_seconds', 0.0):.1f}s")
        w(f"- **Split**: `{split.get('name', '')}` — "
          f"Train {split.get('train')} | Validation {split.get('validation')} "
          f"| OOS {split.get('oos')}")
        w("")

        # ---- funnel -------------------------------------------------- #
        w("## Factor Gate v1 Funnel")
        w("")
        w("| Stage | Count |")
        w("|---|---:|")
        for key in ("alphas_total", "pairs_backtested", "validation_passed",
                    "oos_passed", "robustness_passed", "final_alphas"):
            w(f"| {key} | {funnel.get(key, 0)} |")
        w("")

        # ---- table 2: alpha ranking ---------------------------------- #
        w("## ② Alpha Ranking (top {})".format(TOP_ALPHAS_IN_MD))
        w("")
        ranking = data.get("alpha_ranking", [])
        if ranking:
            w("| Rank | Alpha | Assets Passed | Mean OOS IC | Mean OOS RankIC "
              "| Mean OOS ICIR | Mean OOS Sharpe | Turnover | Score | Status |")
            w("|---:|---|---:|---:|---:|---:|---:|---:|---:|---|")
            for r in ranking[:TOP_ALPHAS_IN_MD]:
                w("| {} | {} | {}/{} | {} | {} | {} | {:.2f} | {:.3f} | "
                  "{:.4f} | {} |".format(
                    r["rank"], r["alpha_id"], r["assets_passed_count"],
                    len(data.get("cross_asset_matrix", {}).get("assets", [])),
                    _fmt(r["mean_oos_ic"], 4), _fmt(r["mean_oos_rank_ic"], 4),
                    _fmt(r["mean_oos_icir"], 3), r["mean_oos_sharpe"],
                    r["mean_turnover"], r["score"], r["status"]))
        else:
            w("_No alphas were evaluated._")
        w("")

        # ---- table 3: cross-asset matrix ----------------------------- #
        w("## ③ Cross-Asset Alpha Matrix (OOS ICIR, `*` = gate passed)")
        w("")
        matrix = data.get("cross_asset_matrix", {})
        assets = matrix.get("assets", [])
        icir = matrix.get("icir", {})
        passed = matrix.get("passed", {})
        if assets and icir:
            w("| Alpha | " + " | ".join(assets) + " |")
            w("|---|" + "---:|" * len(assets))
            for alpha_id in sorted(icir):
                cells = []
                for a in assets:
                    v = icir[alpha_id].get(a)
                    cell = "·" if v is None else f"{v:+.2f}"
                    if passed.get(alpha_id, {}).get(a):
                        cell += "\\*"
                    cells.append(cell)
                w(f"| {alpha_id} | " + " | ".join(cells) + " |")
        else:
            w("_No cross-asset matrix available._")
        w("")

        # ---- pair ranking --------------------------------------------- #
        w("## Gate-Passing (Alpha, Asset) Pairs (top {})".format(
            TOP_PAIRS_IN_MD))
        w("")
        pairs = data.get("pair_ranking", [])
        if pairs:
            w("| Rank | Alpha | Asset | OOS IC | OOS RankIC | OOS ICIR | "
              "OOS Sharpe | OOS Return | MaxDD | Turnover | Score |")
            w("|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
            for r in pairs[:TOP_PAIRS_IN_MD]:
                w("| {} | {} | {} | {} | {} | {} | {:.2f} | {:.1%} | {:.1%} | "
                  "{:.3f} | {:.4f} |".format(
                    r["rank"], r["alpha_id"], r["asset"],
                    _fmt(r.get("oos_ic"), 4), _fmt(r.get("oos_rank_ic"), 4),
                    _fmt(r.get("oos_icir"), 3), r.get("oos_sharpe", 0.0),
                    r.get("oos_return", 0.0), r.get("max_drawdown", 0.0),
                    r.get("turnover_per_bar", 0.0), r.get("score", 0.0)))
        else:
            w("_No (alpha, asset) pair passed the 16-item Factor Gate. This "
              "is a valid research result — the Gate was not relaxed._")
        w("")

        # ---- table 4: convergence ------------------------------------- #
        conv = data.get("convergence", {})
        w("## ④ Strategy x Factor Candidates (convergence)")
        w("")
        if conv.get("strategy_report_found"):
            w(f"- Strategy experiment: `{conv.get('strategy_experiment_id')}` "
              f"({conv.get('strategy_final_candidates', 0)} final candidates)")
        else:
            w("- _No strategy discovery report found — factor-only output._")
        if conv.get("factor_candidates"):
            w(f"- Factor candidates (gate passed): "
              f"{', '.join(conv['factor_candidates'])}")
        if conv.get("factor_watch_list"):
            w(f"- Factor watch list (top ICIR, gate not passed): "
              f"{', '.join(conv['factor_watch_list'])}")
            for alpha_id, assets in conv.get("watch_list_assets",
                                             {}).items():
                if assets:
                    w(f"  - {alpha_id}: strongest on {', '.join(assets)}")
        w("")
        combos = conv.get("combinations", [])
        if combos:
            w("| Candidate | Strategy | Factor | Shared Assets | Strategy "
              "Score | Alpha Score | Combined | Status | Next Step |")
            w("|---|---|---|---|---:|---:|---:|---|---|")
            for c in combos:
                w("| {} | {} | {} | {} | {:.4f} | {:.4f} | {:.4f} | {} | "
                  "{} |".format(
                    c["label"], c["strategy_id"], c["alpha_id"],
                    ",".join(c["shared_assets"]), c["strategy_score"],
                    c["alpha_score"], c["combined_score"], c["status"],
                    c["next_step"]))
        else:
            w("_No strategy x factor combination available (one or both "
              "tracks produced no survivors)._")
        w("")

        # ---- reject reasons ------------------------------------------- #
        reasons = data.get("reject_reasons", {})
        w("## Reject Reasons (per alpha-asset pair)")
        w("")
        if reasons:
            w("| Gate check | Failures |")
            w("|---|---:|")
            for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
                w(f"| {reason} | {count} |")
        else:
            w("_No rejections._")
        w("")
        w("---")
        w("_Generated by ICYQuant Factor Discovery Engine v1 — OOS data was "
          "never used for factor selection; scores rank, they never relax "
          "the Gate._")
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def _mean(vals: list[float]) -> Optional[float]:
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 6) if vals else None


def _norm1(x: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.5
    return (min(hi, max(lo, x)) - lo) / (hi - lo)


def _fmt(v: Optional[float], nd: int) -> str:
    return "·" if v is None else f"{v:+.{nd}f}"
