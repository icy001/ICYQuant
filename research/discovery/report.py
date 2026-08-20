"""Discovery Report — the human-readable output of Strategy Discovery Lab v1.

Produces a JSON snapshot (fully machine-readable) and a Markdown report with:

    - the funnel (generated -> backtested -> validated -> OOS -> robustness),
    - the Top 10 candidates with full Train / Validation / OOS detail,
    - family analysis (mean OOS Sharpe per strategy family),
    - the asset x family matrix (which structures work where),
    - reject-reason breakdown,
    - the candidate lifecycle stage summary.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .candidate import Candidate
from .engine import DiscoveryExperimentResult
from .spec import DISCOVERY_SPEC_V1

FAMILY_ORDER = ("Trend", "Momentum", "Breakout", "Mean Reversion", "Hybrid")


class DiscoveryReport:
    """Builds and persists the JSON + Markdown report for an experiment."""

    def __init__(self, output_dir: Optional[Path] = None,
                 spec=None) -> None:
        self.output_dir = output_dir or (Path(__file__).resolve().parent / "output")
        self.spec = spec or DISCOVERY_SPEC_V1

    # ------------------------------------------------------------------ #
    def build(self, result: DiscoveryExperimentResult,
              candidates: list[Candidate]) -> dict[str, Any]:
        """Assemble the full report dict (JSON-serialisable)."""
        data = result.to_dict()
        data["report_generated_at"] = datetime.now(timezone.utc).isoformat()
        by_id = {c.candidate_id: c for c in candidates}

        data["top_candidates_detail"] = [
            self._top_row(s, result, by_id) for s in result.top_candidates
        ]
        data["candidate_lifecycle"] = self._lifecycle(result, by_id)
        data["lifecycle_summary"] = self._lifecycle_summary(data["candidate_lifecycle"])
        return data

    # ------------------------------------------------------------------ #
    def _top_row(self, score: dict[str, Any],
                 result: DiscoveryExperimentResult,
                 by_id: dict[str, Candidate]) -> dict[str, Any]:
        cid = score["candidate_id"]
        assets = score["assets_passed"]
        cand = by_id.get(cid)
        seg_means: dict[str, dict[str, float]] = {}
        for seg in ("train", "validation", "oos"):
            vals = [result.outcomes[cid][a]["segments"][seg] for a in assets]
            seg_means[seg] = {
                "total_return": sum(v["total_return"] for v in vals) / len(vals),
                "sharpe": sum(v["sharpe"] for v in vals) / len(vals),
                "max_drawdown": sum(v["max_drawdown"] for v in vals) / len(vals),
                "profit_factor": sum(v["profit_factor"] for v in vals) / len(vals),
                "trade_count": int(sum(v["trade_count"] for v in vals) / len(vals)),
            }
        return {
            "candidate_id": cid,
            "family": score["family"],
            "structure_id": score["structure_id"],
            "params": score["params"],
            "assets": assets,
            "train": seg_means["train"],
            "validation": seg_means["validation"],
            "oos": seg_means["oos"],
            "total_score": score["total_score"],
            "status": "CANDIDATE",
        }

    # ------------------------------------------------------------------ #
    def _lifecycle(self, result: DiscoveryExperimentResult,
                   by_id: dict[str, Candidate]) -> dict[str, Any]:
        """Per-candidate lifecycle stage + status."""
        th = self.spec.gate_thresholds
        min_assets = th["min_assets_passed"]
        out: dict[str, Any] = {}
        for cid in result.outcomes:
            per_asset = result.outcomes[cid]
            n_full = sum(1 for od in per_asset.values() if od["passed"])
            n_oos = sum(1 for od in per_asset.values()
                        if _passed_through(od, "oos_performance"))
            n_val = sum(1 for od in per_asset.values()
                        if _passed_through(od, "validation_performance"))
            if n_full >= min_assets:
                stage, status = "ROBUSTNESS_TESTED", "CANDIDATE"
            elif n_oos >= min_assets:
                stage, status = "OOS_TESTED", "REJECTED"
            elif n_val >= min_assets:
                stage, status = "VALIDATED", "REJECTED"
            elif n_full + n_oos + n_val > 0:
                stage, status = "BACKTESTED", "REJECTED"
            else:
                stage, status = "GENERATED", "REJECTED"
            # most common first-failure reason across the candidate's pairs
            reasons: dict[str, int] = {}
            for od in per_asset.values():
                if not od["passed"] and od["fail_reason"]:
                    reasons[od["fail_reason"]] = reasons.get(od["fail_reason"], 0) + 1
            fail_reason = max(reasons, key=reasons.get) if reasons else ""
            cand = by_id.get(cid)
            out[cid] = {
                "family": cand.family if cand else "",
                "structure_id": cand.structure_id if cand else "",
                "assets_passed": n_full,
                "assets_total": len(per_asset),
                "stage": stage,
                "status": status,
                "fail_reason": fail_reason,
            }
        return out

    # ------------------------------------------------------------------ #
    @staticmethod
    def _lifecycle_summary(lifecycle: dict[str, Any]) -> dict[str, int]:
        summary: dict[str, int] = {}
        for info in lifecycle.values():
            key = f"{info['status']}@{info['stage']}"
            summary[key] = summary.get(key, 0) + 1
        return summary

    # ------------------------------------------------------------------ #
    def save(self, data: dict[str, Any], experiment_id: str) -> tuple[Path, Path]:
        """Write report.json and report.md under output/<experiment_id>/."""
        out_dir = self.output_dir / experiment_id
        out_dir.mkdir(parents=True, exist_ok=True)
        json_path = out_dir / "report.json"
        json_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        md_path = out_dir / "report.md"
        md_path.write_text(self.to_markdown(data), encoding="utf-8")
        return json_path, md_path

    # ------------------------------------------------------------------ #
    def to_markdown(self, data: dict[str, Any]) -> str:
        funnel = data["funnel"]
        split = data.get("split", {})
        lines: list[str] = []
        w = lines.append
        w("# ICYQuant — Strategy Discovery Lab v1 Report")
        w("")
        w(f"- **Experiment**: `{data['experiment_id']}`")
        w(f"- **Spec version**: `{data.get('spec_version')}`")
        w(f"- **Generated at**: `{data.get('report_generated_at', '')}`")
        w(f"- **Runtime**: {data.get('runtime_seconds', 0.0):.1f}s")
        w(f"- **Split**: `{split.get('name', '')}` — "
          f"Train {split.get('train')} | Validation {split.get('validation')} | "
          f"OOS {split.get('oos')}")
        w("")
        w("## Discovery Gate v1 Funnel")
        w("")
        w("| Stage | Count |")
        w("|---|---:|")
        for key in ("candidates_total", "candidates_backtested",
                    "validation_passed", "oos_passed", "robustness_passed",
                    "final_candidates"):
            w(f"| {key} | {funnel.get(key, 0)} |")
        w("")

        top = data.get("top_candidates_detail", [])
        w("## Top 10 Candidates")
        w("")
        if top:
            w("| ID | Family | Structure | Assets | Train R | Val R | OOS R | "
              "Sharpe | MaxDD | PF | Trades | Score | Status |")
            w("|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
            for r in top:
                w("| {} | {} | {} | {} | {:.1%} | {:.1%} | {:.1%} | {:.2f} | "
                  "{:.1%} | {:.2f} | {} | {:.3f} | {} |".format(
                    r["candidate_id"], r["family"], r["structure_id"],
                    ",".join(r["assets"]),
                    r["train"]["total_return"], r["validation"]["total_return"],
                    r["oos"]["total_return"], r["oos"]["sharpe"],
                    r["oos"]["max_drawdown"], r["oos"]["profit_factor"],
                    r["oos"]["trade_count"], r["total_score"], r["status"]))
        else:
            w("_No candidates passed the Discovery Gate v1. This is a valid "
              "research result — the Gate was not relaxed._")
        w("")

        fam = data.get("family_analysis", {})
        w("## Strategy Family Analysis (final candidates)")
        w("")
        if fam:
            w("| Family | Count | Mean OOS Sharpe | Min | Max |")
            w("|---|---:|---:|---:|---:|")
            for f in FAMILY_ORDER:
                if f in fam:
                    v = fam[f]
                    w(f"| {f} | {v['count']} | {v['mean_oos_sharpe']:.3f} | "
                      f"{v['min_oos_sharpe']:.3f} | {v['max_oos_sharpe']:.3f} |")
        else:
            w("_No family-level survivors._")
        w("")

        matrix = data.get("asset_family_matrix", {})
        w("## Asset x Family Matrix (final candidates per asset)")
        w("")
        if matrix:
            w("| Asset | Trend | Momentum | Breakout | Mean Reversion | Hybrid |")
            w("|---|---:|---:|---:|---:|---:|")
            for asset, m in matrix.items():
                fc = m["family_counts"]
                w("| {} | {} | {} | {} | {} | {} |".format(
                    asset,
                    _fmt_cell(fc.get("Trend")), _fmt_cell(fc.get("Momentum")),
                    _fmt_cell(fc.get("Breakout")),
                    _fmt_cell(fc.get("Mean Reversion")),
                    _fmt_cell(fc.get("Hybrid"))))
        w("")

        reasons = data.get("reject_reasons", {})
        w("## Reject Reasons (per candidate-asset pair)")
        w("")
        if reasons:
            w("| Gate check | Failures |")
            w("|---|---:|")
            for reason, count in sorted(reasons.items(),
                                        key=lambda kv: -kv[1]):
                w(f"| {reason} | {count} |")
        else:
            w("_No rejections._")
        w("")

        lc = data.get("lifecycle_summary", {})
        w("## Candidate Lifecycle Summary")
        w("")
        if lc:
            w("| Status | Stage | Count |")
            w("|---|---:|---:|")
            for k, v in sorted(lc.items(), key=lambda kv: -kv[1]):
                status, _, stage = k.partition("@")
                w(f"| {status} | {stage} | {v} |")
        w("")
        w("---")
        w("_Generated by ICYQuant Discovery Engine v1 — OOS data was never "
          "used for parameter selection._")
        return "\n".join(lines)


def _passed_through(outcome: dict[str, Any], check_name: str) -> bool:
    for chk in outcome["checks"]:
        if not chk["passed"]:
            return False
        if chk["name"] == check_name:
            return True
    return True


def _fmt_cell(v: Optional[int]) -> str:
    return str(v) if v else "0"
