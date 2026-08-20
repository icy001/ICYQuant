"""Discovery Engine — orchestrates the full Strategy Discovery Lab v1 flow.

Pipeline (strictly sequential, no OOS leakage):

    generate 300 candidates
        -> per (candidate, asset): Train / Validation / OOS backtests
        -> walk-forward windows (inside Train+Validation only)
        -> parameter stability (same-structure neighbourhood)
        -> 16-item Discovery Gate v1
        -> candidate-level aggregation (>= min_assets_passed)
        -> multi-factor ranking -> Top candidates
        -> family analysis + report

The OOS segment never participates in parameter selection: parameters are
fixed by the sealed spec, and OOS is only ever *measured* at the very end.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any, Optional

from ..data.bar import Bar
from ..data.csv_provider import CsvMarketDataProvider
from ..data.types import TimeFrame
from .backtest import BacktestResult, DiscoveryBacktest
from .candidate import Candidate
from .cost import CostModel, DEFAULT_COST_MODEL
from .gate import DiscoveryGate
from .generator import CandidateGenerator
from .indicators import IndicatorLibrary
from .ranking import DiscoveryScore, build_score, rank_candidates
from .robustness import (
    StabilityReport,
    WalkForwardReport,
    WalkForwardWindow,
    parameter_stability,
    walk_forward_check,
)
from .spec import DISCOVERY_SPEC_V1, DiscoverySpec
from .split import (
    ACTIVE_SPLIT,
    TimeSplit,
    build_walk_forward_windows,
)

SEGMENTS = ("train", "validation", "oos")


# --------------------------------------------------------------------------- #
# Result container                                                             #
# --------------------------------------------------------------------------- #
@dataclass
class DiscoveryExperimentResult:
    """Full output of one discovery experiment."""

    experiment_id: str
    spec: dict[str, Any] = field(default_factory=dict)
    split: dict[str, Any] = field(default_factory=dict)
    candidates_total: int = 0
    candidates_backtested: int = 0
    validation_passed: int = 0
    oos_passed: int = 0
    robustness_passed: int = 0
    final_candidates: int = 0
    top_candidates: list[dict[str, Any]] = field(default_factory=list)
    family_analysis: dict[str, Any] = field(default_factory=dict)
    asset_family_matrix: dict[str, Any] = field(default_factory=dict)
    reject_reasons: dict[str, int] = field(default_factory=dict)
    # candidate_id -> asset -> gate outcome dict
    outcomes: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    # candidate_id -> {family, structure_id, params, assets_passed, score}
    ranked: list[dict[str, Any]] = field(default_factory=list)
    runtime_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "spec_version": self.spec.get("version"),
            "split": self.split,
            "funnel": {
                "candidates_total": self.candidates_total,
                "candidates_backtested": self.candidates_backtested,
                "validation_passed": self.validation_passed,
                "oos_passed": self.oos_passed,
                "robustness_passed": self.robustness_passed,
                "final_candidates": self.final_candidates,
            },
            "top_candidates": self.top_candidates,
            "family_analysis": self.family_analysis,
            "asset_family_matrix": self.asset_family_matrix,
            "reject_reasons": self.reject_reasons,
            "ranked": self.ranked,
            "outcomes": self.outcomes,
            "runtime_seconds": round(self.runtime_seconds, 2),
        }


# --------------------------------------------------------------------------- #
# Worker helpers (multiprocessing)                                             #
# --------------------------------------------------------------------------- #
_WORKER: dict[str, Any] = {}


def _init_worker(data_root: Path, split: TimeSplit,
                 windows: list[WalkForwardWindow],
                 cost_config: dict[str, dict[str, float]]) -> None:
    _WORKER["data_root"] = Path(data_root)
    _WORKER["split"] = split
    _WORKER["windows"] = windows
    _WORKER["cost_config"] = cost_config
    _WORKER["provider"] = CsvMarketDataProvider(_WORKER["data_root"])
    _WORKER["bars"] = {}
    _WORKER["arrays"] = {}
    _WORKER["libs"] = {}


def _asset_data(asset: str) -> tuple[list[Bar], tuple[list, list, list], IndicatorLibrary]:
    if asset in _WORKER["bars"]:
        return _WORKER["bars"][asset], _WORKER["arrays"][asset], _WORKER["libs"][asset]
    provider = _WORKER["provider"]
    bars = provider.load_bars(asset, TimeFrame.H1)
    arrays = ([b.close for b in bars], [b.high for b in bars], [b.low for b in bars])
    lib = IndicatorLibrary()
    _WORKER["bars"][asset] = bars
    _WORKER["arrays"][asset] = arrays
    _WORKER["libs"][asset] = lib
    return bars, arrays, lib


def _worker_run(task: tuple[str, Candidate]) -> dict[str, Any]:
    """Backtest one (asset, candidate) pair: train/val/oos + walk-forward."""
    asset, candidate = task
    split = _WORKER["split"]
    windows = _WORKER["windows"]
    cost = CostModel(_WORKER["cost_config"])
    bt = DiscoveryBacktest(cost_model=cost)
    ca = replace(candidate, asset=asset)

    try:
        bars, arrays, lib = _asset_data(asset)
    except Exception as exc:  # missing/broken data -> dataset gate fails
        return {
            "candidate_id": candidate.candidate_id,
            "asset": asset,
            "structure_id": candidate.structure_id,
            "params": candidate.parameters,
            "dataset_ok": False,
            "error": str(exc),
            "train": None, "validation": None, "oos": None,
            "wf": [],
        }

    one_way_bps = cost.one_way_bps(asset)
    results: dict[str, BacktestResult] = {}
    for seg in SEGMENTS:
        results[seg] = bt.run(bars, ca, split, seg, library=lib,
                              one_way_bps=one_way_bps, arrays=arrays)

    wf: list[BacktestResult] = []
    for w in windows:
        wf.append(bt.run(bars, ca, split, f"wf_{w.index}_oos", library=lib,
                         one_way_bps=one_way_bps, arrays=arrays,
                         start=w.oos_start, end=w.oos_end))

    return {
        "candidate_id": candidate.candidate_id,
        "asset": asset,
        "structure_id": candidate.structure_id,
        "params": candidate.parameters,
        "dataset_ok": True,
        "train": results["train"],
        "validation": results["validation"],
        "oos": results["oos"],
        "wf": wf,
    }


# --------------------------------------------------------------------------- #
# Engine                                                                       #
# --------------------------------------------------------------------------- #
class DiscoveryEngine:
    """Orchestrates a full discovery experiment."""

    def __init__(self, spec: Optional[DiscoverySpec] = None,
                 data_root: Optional[Path] = None,
                 jobs: int = 1,
                 seed: int = 42,
                 wf_config: Optional[dict[str, Any]] = None) -> None:
        self.spec = spec or DISCOVERY_SPEC_V1
        self.jobs = max(1, jobs)
        self.seed = seed
        self.data_root = Path(data_root) if data_root else (
            Path(__file__).resolve().parents[2] / "data" / "processed"
        )
        self.split = ACTIVE_SPLIT
        self.windows = build_walk_forward_windows(self.split, **(wf_config or {}))
        self.cost_model = DEFAULT_COST_MODEL
        self.gate = DiscoveryGate(self.spec.gate_thresholds)
        self.generator = CandidateGenerator(self.spec, seed=seed)
        self._n_indicators_extra = self.spec.gate_thresholds.get("complexity_base", 4)

    # ------------------------------------------------------------------ #
    def load_bars(self, asset: str) -> list[Bar]:
        """Load a single asset's full history (main-process convenience)."""
        return CsvMarketDataProvider(self.data_root).load_bars(asset, TimeFrame.H1)

    # ------------------------------------------------------------------ #
    def run_experiment(self, experiment_id: str,
                       limit: Optional[int] = None) -> DiscoveryExperimentResult:
        """Run the full experiment and return the result container."""
        t0 = time.time()
        result = DiscoveryExperimentResult(
            experiment_id=experiment_id,
            spec=self.spec.to_dict(),
            split=self.split.to_dict(),
            candidates_total=0,
        )

        candidates = self.generator.generate()
        if limit is not None:
            candidates = candidates[:limit]
        result.candidates_total = len(candidates)
        self.candidates = candidates
        self._candidates_by_id = {c.candidate_id: c for c in candidates}

        tasks = [(asset, c) for c in candidates for asset in self.spec.universe]
        outcomes_by_pair: dict[tuple[str, str], dict[str, Any]] = {}

        if self.jobs == 1:
            _init_worker(self.data_root, self.split, self.windows,
                         self.spec.cost_config)
            for task in tasks:
                outcomes_by_pair[(task[1].candidate_id, task[0])] = _worker_run(
                    task)
        else:
            with ProcessPoolExecutor(
                max_workers=self.jobs,
                initializer=_init_worker,
                initargs=(self.data_root, self.split, self.windows,
                          self.spec.cost_config),
            ) as pool:
                futures = {pool.submit(_worker_run, t): t for t in tasks}
                for fut in as_completed(futures):
                    payload = fut.result()
                    outcomes_by_pair[(payload["candidate_id"], payload["asset"])] = payload

        result.candidates_backtested = sum(
            1 for p in outcomes_by_pair.values() if p.get("dataset_ok")
        )

        # ---- phase 2: stability / walk-forward / gate (main process) ---- #
        # collect OOS Sharpes per (structure, asset) for the neighbourhood
        oos_by_pair: dict[tuple[str, str], BacktestResult] = {}
        neigh_sharpes: dict[tuple[str, str], list[float]] = {}
        for (cid, asset), payload in outcomes_by_pair.items():
            if not payload.get("dataset_ok"):
                continue
            oos = payload["oos"]
            oos_by_pair[(cid, asset)] = oos
            key = (payload["structure_id"], asset)
            neigh_sharpes.setdefault(key, []).append(oos.metrics.sharpe)

        # per (candidate, asset) gate outcomes
        candidates_by_id = {c.candidate_id: c for c in candidates}
        for cid, asset in outcomes_by_pair:
            payload = outcomes_by_pair[(cid, asset)]
            candidate = candidates_by_id[cid]
            if not payload.get("dataset_ok"):
                empty = lambda seg: BacktestResult(
                    candidate_id=cid, asset=asset,
                    structure_id=candidate.structure_id, segment=seg)
                outcome = self.gate.evaluate(
                    candidate, False,
                    empty("train"), empty("validation"), empty("oos"),
                    StabilityReport(candidate_id=cid,
                                    structure_id=candidate.structure_id,
                                    asset=asset),
                    WalkForwardReport(candidate_id=cid, asset=asset),
                    self.spec.cost_config[asset],
                )
            else:
                oos = payload["oos"]
                stability = parameter_stability(
                    cid, payload["structure_id"], asset,
                    neigh_sharpes[(payload["structure_id"], asset)],
                    min_positive_frac=self.spec.gate_thresholds[
                        "stability_min_positive_frac"],
                    max_cv=self.spec.gate_thresholds["stability_max_cv"],
                )
                wf_report = walk_forward_check(
                    cid, asset, payload["wf"],
                    min_positive_frac=self.spec.gate_thresholds[
                        "wf_min_positive_windows"],
                )
                outcome = self.gate.evaluate(
                    candidate, True,
                    payload["train"], payload["validation"], oos,
                    stability, wf_report,
                    self.spec.cost_config[asset],
                )
            entry = outcome.to_dict()
            entry["segments"] = {
                SEGMENTS[i]: _seg_summary(payload.get(seg))
                for i, seg in enumerate(SEGMENTS)
            }
            result.outcomes.setdefault(cid, {})[asset] = entry

        # ---- funnel counts + reject reasons ---- #
        th = self.spec.gate_thresholds
        min_assets = th["min_assets_passed"]
        for cid in result.outcomes:
            per_asset = result.outcomes[cid]
            def _count(up_to: str) -> int:
                n = 0
                for asset, od in per_asset.items():
                    if _passed_through(od, up_to):
                        n += 1
                return n
            if _count("validation_performance") >= min_assets:
                result.validation_passed += 1
            if _count("oos_performance") >= min_assets:
                result.oos_passed += 1
            if sum(1 for od in per_asset.values() if od["passed"]) >= min_assets:
                result.robustness_passed += 1
            # reject reasons across failing pairs
            for od in per_asset.values():
                if not od["passed"] and od["fail_reason"]:
                    result.reject_reasons[od["fail_reason"]] = (
                        result.reject_reasons.get(od["fail_reason"], 0) + 1)

        # ---- candidate-level aggregation + ranking ---- #
        result.final_candidates = result.robustness_passed
        survivors: list[DiscoveryScore] = []
        for cid, per_asset in result.outcomes.items():
            passed_assets = [a for a, od in per_asset.items() if od["passed"]]
            if len(passed_assets) < min_assets:
                continue
            cand = candidates_by_id[cid]
            sharpe = _mean_metric(per_asset, passed_assets, "sharpe")
            oos_return = _mean_metric(per_asset, passed_assets, "total_return")
            dd = _mean_metric(per_asset, passed_assets, "max_drawdown")
            pf = _mean_metric(per_asset, passed_assets, "profit_factor")
            trades = int(sum(per_asset[a]["oos_metrics"]["trade_count"]
                             for a in passed_assets) / len(passed_assets))
            stability_mean = _stability_fraction(per_asset, passed_assets)
            n_params = len(cand.parameters)
            survivors.append(build_score(
                candidate_id=cid,
                family=cand.family,
                structure_id=cand.structure_id,
                params=cand.parameters,
                assets_passed=passed_assets,
                oos_sharpe=sharpe,
                oos_return=oos_return,
                max_drawdown=dd,
                profit_factor=pf,
                stability=stability_mean,
                trade_count=trades,
                n_indicators=self._n_indicators_extra,
                n_params=n_params,
            ))

        ranked = rank_candidates(survivors, self.spec.score_weights)
        result.top_candidates = [s.to_dict() for s in ranked[:10]]
        result.ranked = [s.to_dict() for s in ranked]

        self._family_analysis(result, ranked)
        result.runtime_seconds = time.time() - t0
        return result

    # ------------------------------------------------------------------ #
    def _family_analysis(self, result: DiscoveryExperimentResult,
                         ranked: list[DiscoveryScore]) -> None:
        """Per-family and per-asset x family summary over ranked survivors."""
        fam_stats: dict[str, list[float]] = {}
        for s in ranked:
            fam_stats.setdefault(s.family, []).append(s.oos_sharpe)
        family_analysis: dict[str, Any] = {}
        for fam, sharpes in fam_stats.items():
            family_analysis[fam] = {
                "count": len(sharpes),
                "mean_oos_sharpe": round(sum(sharpes) / len(sharpes), 4),
                "min_oos_sharpe": round(min(sharpes), 4),
                "max_oos_sharpe": round(max(sharpes), 4),
            }
        result.family_analysis = family_analysis

        # asset x family: how many final candidates per family on each asset,
        # plus the mean OOS Sharpe of those candidates
        matrix: dict[str, dict[str, Any]] = {}
        for asset in self.spec.universe:
            fam_counts: dict[str, int] = {}
            fam_sharpe: dict[str, list[float]] = {}
            for cid in result.outcomes:
                od = result.outcomes[cid].get(asset)
                if od is None or not od["passed"]:
                    continue
                cand = self.generator_family(cid)
                if cand is None:
                    continue
                fam = cand.family
                fam_counts[fam] = fam_counts.get(fam, 0) + 1
                fam_sharpe.setdefault(fam, []).append(od["oos_metrics"]["sharpe"])
            matrix[asset] = {
                "family_counts": fam_counts,
                "family_mean_sharpe": {
                    f: round(sum(v) / len(v), 4) for f, v in fam_sharpe.items()
                },
            }
        result.asset_family_matrix = matrix

    # ------------------------------------------------------------------ #
    def generator_family(self, candidate_id: str) -> Optional[Candidate]:
        """Look up a generated candidate by id (for report aggregation)."""
        if getattr(self, "_candidates_by_id", None) is None:
            self._candidates_by_id = {
                c.candidate_id: c for c in self.generator.generate()
            }
        return self._candidates_by_id.get(candidate_id)


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def _passed_through(outcome: dict[str, Any], check_name: str) -> bool:
    for chk in outcome["checks"]:
        if not chk["passed"]:
            return False
        if chk["name"] == check_name:
            return True
    return True  # everything through the last check passed


def _mean_metric(per_asset: dict[str, dict[str, Any]],
                 passed_assets: list[str], key: str) -> float:
    vals = [float(per_asset[a]["oos_metrics"].get(key, 0.0) or 0.0)
            for a in passed_assets]
    return sum(vals) / len(vals) if vals else 0.0


def _seg_summary(backtest_result: Optional[BacktestResult]) -> dict[str, Any]:
    """Compact per-segment metrics for the report."""
    if backtest_result is None:
        return {"total_return": 0.0, "sharpe": 0.0, "max_drawdown": 0.0,
                "profit_factor": 0.0, "trade_count": 0}
    m = backtest_result.metrics
    return {
        "total_return": round(m.total_return, 6),
        "sharpe": round(m.sharpe, 4),
        "max_drawdown": round(m.max_drawdown, 6),
        "profit_factor": round(m.profit_factor, 4),
        "trade_count": m.trade_count,
    }


def _stability_fraction(per_asset: dict[str, dict[str, Any]],
                        passed_assets: list[str]) -> float:
    """Mean of the 'parameter stability' pass flag across passed assets."""
    vals = []
    for a in passed_assets:
        for chk in per_asset[a]["checks"]:
            if chk["name"] == "parameter_stability":
                vals.append(1.0 if chk["passed"] else 0.0)
                break
    return sum(vals) / len(vals) if vals else 0.0
