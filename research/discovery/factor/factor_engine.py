"""Factor Discovery Engine — orchestrates the Alpha101 track.

Pipeline per (alpha, asset) pair (strictly causal, OOS never touched before
the final measurement):

    compute factor over the full history (causal rolling operators)
        -> coverage check
        -> rolling z-score -> Schmitt-trigger positions
        -> orient the portfolio by the sign of the TRAIN IC
           (direction-agnostic |IC| checks require a direction-aware
            portfolio; the sign is a train-only decision)
        -> net returns (per-asset costs always applied)
        -> per segment (train / validation / oos):
             IC / Rank IC / block-IC series / ICIR
             long-short portfolio metrics (net of per-asset costs)
        -> walk-forward windows (inside train + validation only)
        -> stability (train IC sign consistency across quarters)
        -> 16-item Factor Discovery Gate
        -> alpha-level aggregation (>= min_assets_passed assets)
        -> multi-factor ranking
"""
from __future__ import annotations

import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ...data.bar import Bar
from ...data.csv_provider import CsvMarketDataProvider
from ...data.types import TimeFrame
from ..cost import CostModel, DEFAULT_COST_MODEL
from ..split import ACTIVE_SPLIT, TimeSplit, build_split, build_walk_forward_windows
from .evaluation import SegmentIC, segment_ic, sign_consistency
from .factor_backtest import (
    net_returns,
    orient_positions,
    portfolio_metrics,
    positions_from_z,
    rolling_zscore,
)
from .factor_gate import FactorGate, FactorGateOutcome, PairEvidence
from .factor_spec import (
    FACTOR_SPEC_V1,
    FactorSpec,
    IC_BLOCK_BARS,
    Z_WINDOW,
    STABILITY_QUARTERS,
)
from .formulas import ALPHA_IDS, MarketData, compute_alpha
from .operators import set_rank_window

SEGMENTS = ("train", "validation", "oos")


# --------------------------------------------------------------------------- #
# Result containers                                                            #
# --------------------------------------------------------------------------- #
@dataclass
class FactorExperimentResult:
    experiment_id: str
    spec: dict[str, Any] = field(default_factory=dict)
    split: dict[str, Any] = field(default_factory=dict)
    alphas_total: int = 0
    pairs_backtested: int = 0
    validation_passed: int = 0
    oos_passed: int = 0
    robustness_passed: int = 0
    final_alphas: int = 0
    ranked_pairs: list[dict[str, Any]] = field(default_factory=list)
    alpha_summary: list[dict[str, Any]] = field(default_factory=list)
    cross_asset_matrix: dict[str, dict[str, Any]] = field(default_factory=dict)
    reject_reasons: dict[str, int] = field(default_factory=dict)
    outcomes: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    runtime_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "track": "factor",
            "spec": self.spec,
            "split": self.split,
            "funnel": {
                "alphas_total": self.alphas_total,
                "pairs_backtested": self.pairs_backtested,
                "validation_passed": self.validation_passed,
                "oos_passed": self.oos_passed,
                "robustness_passed": self.robustness_passed,
                "final_alphas": self.final_alphas,
            },
            "ranked_pairs": self.ranked_pairs,
            "alpha_summary": self.alpha_summary,
            "cross_asset_matrix": self.cross_asset_matrix,
            "reject_reasons": self.reject_reasons,
            "outcomes": self.outcomes,
            "runtime_seconds": round(self.runtime_seconds, 2),
        }


# --------------------------------------------------------------------------- #
# Workers (multiprocessing)                                                    #
# --------------------------------------------------------------------------- #
_FWORKER: dict[str, Any] = {}


def _finit_worker(data_root: Path, split: TimeSplit,
                  windows: list[Any],
                  cost_config: dict[str, dict[str, float]],
                  timeframe: TimeFrame = TimeFrame.H1,
                  z_window: int = Z_WINDOW,
                  rank_window: Optional[int] = None,
                  ic_block_bars: int = IC_BLOCK_BARS) -> None:
    _FWORKER["data_root"] = Path(data_root)
    _FWORKER["split"] = split
    _FWORKER["windows"] = windows
    _FWORKER["cost"] = CostModel(cost_config)
    _FWORKER["provider"] = CsvMarketDataProvider(_FWORKER["data_root"])
    _FWORKER["timeframe"] = timeframe
    _FWORKER["z_window"] = z_window
    _FWORKER["ic_block_bars"] = ic_block_bars
    # rank()/scale() read the module-level window at call time
    if rank_window is not None:
        set_rank_window(rank_window)
    else:
        set_rank_window(250)
    _FWORKER["md"] = {}
    _FWORKER["bars"] = {}
    _FWORKER["dates"] = {}


def _fmarket_data(asset: str) -> Optional[MarketData]:
    if asset in _FWORKER["md"]:
        return _FWORKER["md"][asset]
    provider: CsvMarketDataProvider = _FWORKER["provider"]
    bars: list[Bar] = provider.load_bars(asset, _FWORKER["timeframe"])
    md = MarketData(
        open_=[b.open for b in bars],
        high=[b.high for b in bars],
        low=[b.low for b in bars],
        close=[b.close for b in bars],
        volume=[b.volume for b in bars],
    )
    _FWORKER["bars"][asset] = bars
    _FWORKER["md"][asset] = md
    return md


def _fdates(asset: str) -> list[Any]:
    """Calendar dates per bar (cached separately: MarketData uses __slots__)."""
    if asset not in _FWORKER["dates"]:
        _fmarket_data(asset)  # ensures the bars are cached
        bars: list[Bar] = _FWORKER["bars"][asset]
        _FWORKER["dates"][asset] = [b.timestamp.date() for b in bars]
    return _FWORKER["dates"][asset]


def _segment_indices(dates: list[Any], split: TimeSplit,
                     segment: str) -> list[int]:
    start, end = split.spans[segment]
    return [i for i, d in enumerate(dates) if start <= d <= end]


def _range_indices(dates: list[Any], start, end) -> list[int]:
    return [i for i, d in enumerate(dates) if start <= d <= end]


def _worker_pair(task: tuple[str, str]) -> dict[str, Any]:
    """Evaluate one (alpha, asset) pair end-to-end (except the gate)."""
    alpha_id, asset = task
    split: TimeSplit = _FWORKER["split"]
    windows = _FWORKER["windows"]
    cost: CostModel = _FWORKER["cost"]
    base = {
        "alpha_id": alpha_id,
        "asset": asset,
        "dataset_ok": False,
        "error": None,
    }
    try:
        md = _fmarket_data(asset)
    except Exception as exc:
        base["error"] = str(exc)
        return base

    try:
        factor = compute_alpha(alpha_id, md)
    except Exception as exc:  # formula crash -> fail closed
        base["error"] = f"compute: {exc}"
        return base

    n = len(factor)
    valid = sum(1 for v in factor if v is not None and v == v)
    coverage = valid / n if n else 0.0

    dates = _fdates(asset)
    z = rolling_zscore(factor, window=_FWORKER["z_window"])
    one_way_bps = cost.one_way_bps(asset)

    seg_idx = {seg: _segment_indices(dates, split, seg) for seg in SEGMENTS}
    if any(not seg_idx[seg] for seg in SEGMENTS):
        base["error"] = "empty segment"
        return base
    base["dataset_ok"] = True

    # bar returns for IC alignment (delay-1 handled inside align)
    bar_returns: list[Any] = [None] * n
    for i in range(1, n):
        if md.close[i - 1] not in (None, 0) and md.close[i] is not None:
            bar_returns[i] = md.close[i] / md.close[i - 1] - 1.0

    # train IC first: the long-short portfolio is oriented by its sign
    # (train-only decision; validation / OOS are never consulted)
    blocks = _FWORKER["ic_block_bars"]
    train_ic = segment_ic(factor, bar_returns, seg_idx["train"],
                          block_bars=blocks).ic
    positions, orientation = orient_positions(positions_from_z(z), train_ic)
    net = net_returns(md.close, positions, one_way_bps / 10_000.0)

    ics: dict[str, SegmentIC] = {}
    pfs = {}
    for seg in SEGMENTS:
        idx = seg_idx[seg]
        ics[seg] = segment_ic(factor, bar_returns, idx, block_bars=blocks)
        pfs[seg] = portfolio_metrics(dates, net, positions, idx)

    stability = sign_consistency(factor, bar_returns, seg_idx["train"],
                                 ics["train"].ic, STABILITY_QUARTERS)

    # walk-forward: long-short return over each window's OOS period
    wf_total = 0
    wf_positive = 0
    for w in windows:
        idx = _range_indices(dates, w.oos_start, w.oos_end)
        if not idx:
            continue
        wf_total += 1
        eq = 1.0
        for t in idx:
            r = net[t]
            if r is not None:
                eq *= (1.0 + r)
        if eq > 1.0:
            wf_positive += 1

    return {
        **base,
        "coverage": coverage,
        "train_ic": ics["train"].to_dict(),
        "validation_ic": ics["validation"].to_dict(),
        "oos_ic": ics["oos"].to_dict(),
        "train_pf": pfs["train"].to_dict(),
        "validation_pf": pfs["validation"].to_dict(),
        "oos_pf": pfs["oos"].to_dict(),
        "wf_windows_total": wf_total,
        "wf_windows_positive": wf_positive,
        "stability_frac": stability,
        "orientation": orientation,
        "one_way_bps": one_way_bps,
        "slippage_bps": cost.breakdown(asset)["slippage_bps"],
    }


# --------------------------------------------------------------------------- #
# Engine                                                                       #
# --------------------------------------------------------------------------- #
class FactorDiscoveryEngine:
    """Orchestrates the full Alpha101 factor discovery experiment."""

    def __init__(self, spec: Optional[FactorSpec] = None,
                 data_root: Optional[Path] = None,
                 jobs: int = 1,
                 wf_config: Optional[dict[str, Any]] = None) -> None:
        self.spec = spec or FACTOR_SPEC_V1
        self.jobs = max(1, jobs)
        self.data_root = Path(data_root) if data_root else (
            Path(__file__).resolve().parents[3] / "data" / "processed"
        )
        # split: spec-carried config, else the strategy line's sealed split
        if self.spec.split:
            self.split = build_split(self.spec.split)
        else:
            self.split = ACTIVE_SPLIT
        # timeframe: "1H" -> H1 (default), "1D" -> D1
        self.timeframe = (TimeFrame.D1 if str(self.spec.timeframe).upper()
                          in ("1D", "D1") else TimeFrame.H1)
        self.z_window = self.spec.z_window or Z_WINDOW
        self.rank_window = self.spec.rank_window
        self.ic_block_bars = self.spec.ic_block_bars or IC_BLOCK_BARS
        self.windows = build_walk_forward_windows(self.split,
                                                  **(wf_config or {}))
        self.cost_model = DEFAULT_COST_MODEL
        self.gate = FactorGate(self.spec.thresholds)

    # ------------------------------------------------------------------ #
    def run_experiment(self, experiment_id: str,
                       limit_alphas: Optional[int] = None,
                       assets: Optional[list[str]] = None) -> FactorExperimentResult:
        t0 = time.time()
        universe = tuple(assets) if assets else self.spec.universe
        alpha_ids = ALPHA_IDS[:limit_alphas] if limit_alphas else list(ALPHA_IDS)
        result = FactorExperimentResult(
            experiment_id=experiment_id,
            spec={**self.spec.to_dict(), "universe": list(universe),
                  "alphas_run": len(alpha_ids)},
            split=self.split.to_dict(),
            alphas_total=len(alpha_ids),
        )

        tasks = [(a, asset) for a in alpha_ids for asset in universe]
        payloads: dict[tuple[str, str], dict[str, Any]] = {}
        worker_args = (self.data_root, self.split, self.windows,
                       self.cost_model.cost_config, self.timeframe,
                       self.z_window, self.rank_window, self.ic_block_bars)
        if self.jobs == 1:
            _finit_worker(*worker_args)
            for task in tasks:
                payloads[task] = _worker_pair(task)
        else:
            with ProcessPoolExecutor(
                max_workers=self.jobs,
                initializer=_finit_worker,
                initargs=worker_args,
            ) as pool:
                futures = {pool.submit(_worker_pair, t): t for t in tasks}
                for fut in as_completed(futures):
                    p = fut.result()
                    payloads[(p["alpha_id"], p["asset"])] = p

        result.pairs_backtested = sum(
            1 for p in payloads.values() if p.get("dataset_ok"))

        # ---- gate per pair (main process) ----------------------------- #
        for (alpha_id, asset), p in sorted(payloads.items()):
            outcome = self._gate_payload(alpha_id, asset, p)
            result.outcomes.setdefault(alpha_id, {})[asset] = outcome.to_dict()

        # ---- funnel + reject reasons ---------------------------------- #
        th = self.spec.thresholds
        min_assets = th["min_assets_passed"]
        for alpha_id, per_asset in result.outcomes.items():
            if self._count_through(per_asset, "validation_performance") >= min_assets:
                result.validation_passed += 1
            if self._count_through(per_asset, "oos_performance") >= min_assets:
                result.oos_passed += 1
            if sum(1 for od in per_asset.values() if od["passed"]) >= min_assets:
                result.robustness_passed += 1
            for od in per_asset.values():
                if not od["passed"] and od["fail_reason"]:
                    result.reject_reasons[od["fail_reason"]] = (
                        result.reject_reasons.get(od["fail_reason"], 0) + 1)
        result.final_alphas = result.robustness_passed

        # ---- ranking + cross-asset matrix ------------------------------ #
        result.ranked_pairs = self._rank_pairs(result.outcomes)
        result.alpha_summary = self._alpha_summary(result.outcomes, universe)
        result.cross_asset_matrix = self._cross_asset_matrix(
            result.outcomes, alpha_ids, universe)
        result.runtime_seconds = time.time() - t0
        return result

    # ------------------------------------------------------------------ #
    def _gate_payload(self, alpha_id: str, asset: str,
                      p: dict[str, Any]) -> FactorGateOutcome:
        if not p.get("dataset_ok"):
            ev = PairEvidence(
                dataset_ok=False, coverage=0.0,
                train_ic=SegmentIC(), validation_ic=SegmentIC(),
                oos_ic=SegmentIC(),
                train_pf=_pf_empty(), validation_pf=_pf_empty(),
                oos_pf=_pf_empty(),
                wf_windows_total=0, wf_windows_positive=0,
                stability_frac=None, one_way_bps=0.0, slippage_bps=0.0)
            out = self.gate.evaluate(alpha_id, asset, ev)
            if p.get("error"):
                out.checks[0].detail = f"error: {p['error']}"
            return out

        def _ic(key: str) -> SegmentIC:
            d = p[key]
            return SegmentIC(
                ic=d.get("ic"), rank_ic=d.get("rank_ic"), ic_mean=d.get("ic_mean"),
                ic_std=d.get("ic_std"), icir=d.get("icir"),
                block_count=d.get("block_count", 0),
                valid_pairs=d.get("valid_pairs", 0))

        def _pf(key: str) -> Any:
            from .factor_backtest import PortfolioMetrics
            d = p[key]
            return PortfolioMetrics(**d)

        ev = PairEvidence(
            dataset_ok=True,
            coverage=p["coverage"],
            train_ic=_ic("train_ic"),
            validation_ic=_ic("validation_ic"),
            oos_ic=_ic("oos_ic"),
            train_pf=_pf("train_pf"),
            validation_pf=_pf("validation_pf"),
            oos_pf=_pf("oos_pf"),
            wf_windows_total=p["wf_windows_total"],
            wf_windows_positive=p["wf_windows_positive"],
            stability_frac=p.get("stability_frac"),
            one_way_bps=p["one_way_bps"],
            slippage_bps=p["slippage_bps"],
        )
        return self.gate.evaluate(alpha_id, asset, ev)

    @staticmethod
    def _count_through(per_asset: dict[str, dict[str, Any]],
                       check_name: str) -> int:
        n = 0
        for od in per_asset.values():
            ok = True
            for chk in od["checks"]:
                if not chk["passed"]:
                    ok = False
                    break
                if chk["name"] == check_name:
                    break
            if ok:
                n += 1
        return n

    # ------------------------------------------------------------------ #
    def _rank_pairs(self, outcomes: dict[str, dict[str, dict[str, Any]]]
                    ) -> list[dict[str, Any]]:
        """Rank all gate-passing (alpha, asset) pairs with the sealed score."""
        rows: list[dict[str, Any]] = []
        for alpha_id, per_asset in outcomes.items():
            for asset, od in per_asset.items():
                if not od["passed"]:
                    continue
                m = od["oos_metrics"]
                train_ic = None
                val_ic = None
                for chk in od["checks"]:
                    if chk["name"] == "train_ic":
                        train_ic = _ic_from_detail(chk["detail"])
                    if chk["name"] == "validation_performance":
                        val_ic = _ic_from_detail(chk["detail"])
                wf_frac = _wf_frac(od)
                st_frac = _stability_frac(od)
                rows.append({
                    "alpha_id": alpha_id,
                    "asset": asset,
                    "oos_ic": m.get("ic"),
                    "oos_rank_ic": m.get("rank_ic"),
                    "oos_icir": m.get("icir"),
                    "oos_sharpe": m.get("sharpe", 0.0),
                    "oos_return": m.get("total_return", 0.0),
                    "max_drawdown": m.get("max_drawdown", 0.0),
                    "turnover_per_bar": m.get("turnover_per_bar", 0.0),
                    "train_ic": train_ic,
                    "validation_ic": val_ic,
                    "wf_frac": wf_frac,
                    "stability_frac": st_frac,
                })

        w = self.spec.score_weights

        def _norm(vals: list[Any], clip_lo: float, clip_hi: float) -> list[float]:
            xs = [min(clip_hi, max(clip_lo, abs(v) if v is not None else 0.0))
                  for v in vals]
            lo, hi = (min(xs), max(xs)) if xs else (0.0, 0.0)
            if hi <= lo:
                return [0.5] * len(xs)
            return [(x - lo) / (hi - lo) for x in xs]

        icir_n = _norm([r["oos_icir"] for r in rows], 0.0, 3.0)
        sharpe_n = _norm([r["oos_sharpe"] for r in rows], 0.0, 5.0)
        ic_n = _norm([r["oos_ic"] for r in rows], 0.0, 0.2)
        val_n = _norm(
            [_val_consistency(r["train_ic"], r["validation_ic"])
             for r in rows], 0.0, 1.0)
        st_n = [r["stability_frac"] if r["stability_frac"] is not None else 0.0
                for r in rows]
        wf_n = [r["wf_frac"] if r["wf_frac"] is not None else 0.0
                for r in rows]
        to_n = _norm([r["turnover_per_bar"] for r in rows], 0.0, 0.5)

        for i, r in enumerate(rows):
            score = (w["oos_icir"] * icir_n[i]
                     + w["oos_sharpe"] * sharpe_n[i]
                     + w["oos_ic"] * ic_n[i]
                     + w["validation_consistency"] * val_n[i]
                     + w["stability"] * st_n[i]
                     + w["walk_forward_frac"] * wf_n[i]
                     + w["turnover_penalty"] * to_n[i])
            r["score"] = round(score, 4)
        rows.sort(key=lambda r: (-r["score"], r["alpha_id"], r["asset"]))
        for i, r in enumerate(rows, 1):
            r["rank"] = i
        return rows

    # ------------------------------------------------------------------ #
    def _alpha_summary(self, outcomes: dict[str, dict[str, dict[str, Any]]],
                       universe: tuple[str, ...]) -> list[dict[str, Any]]:
        """Per-alpha aggregation: assets passed, mean OOS metrics, status."""
        summary: list[dict[str, Any]] = []
        for alpha_id, per_asset in outcomes.items():
            passed = [a for a, od in per_asset.items() if od["passed"]]
            sharpes = [od["oos_metrics"].get("sharpe", 0.0)
                       for a, od in per_asset.items()]
            ics = [od["oos_metrics"].get("ic")
                   for a, od in per_asset.items()
                   if od["oos_metrics"].get("ic") is not None]
            icirs = [od["oos_metrics"].get("icir")
                     for a, od in per_asset.items()
                     if od["oos_metrics"].get("icir") is not None]
            first_fail: dict[str, int] = {}
            for od in per_asset.values():
                if not od["passed"] and od["fail_reason"]:
                    first_fail[od["fail_reason"]] = (
                        first_fail.get(od["fail_reason"], 0) + 1)
            summary.append({
                "alpha_id": alpha_id,
                "assets_passed": passed,
                "assets_passed_count": len(passed),
                "status": "CANDIDATE" if len(passed) >=
                self.spec.thresholds["min_assets_passed"] else "REJECTED",
                "mean_oos_sharpe": round(sum(sharpes) / len(sharpes), 4)
                if sharpes else 0.0,
                "mean_oos_ic": round(sum(ics) / len(ics), 5) if ics else None,
                "mean_oos_icir": round(sum(icirs) / len(icirs), 4)
                if icirs else None,
                "reject_reasons": first_fail,
            })
        summary.sort(key=lambda s: (-s["assets_passed_count"], s["alpha_id"]))
        return summary

    # ------------------------------------------------------------------ #
    def _cross_asset_matrix(self, outcomes: dict[str, dict[str, dict[str, Any]]],
                            alpha_ids: list[str],
                            universe: tuple[str, ...]) -> dict[str, Any]:
        """101 x 9 matrix of per-asset OOS ICIR (+ pass flags)."""
        icir: dict[str, dict[str, Any]] = {}
        passed: dict[str, dict[str, bool]] = {}
        for alpha_id in alpha_ids:
            per_asset = outcomes.get(alpha_id, {})
            icir[alpha_id] = {}
            passed[alpha_id] = {}
            for asset in universe:
                od = per_asset.get(asset)
                if od is None:
                    icir[alpha_id][asset] = None
                    passed[alpha_id][asset] = False
                else:
                    icir[alpha_id][asset] = od["oos_metrics"].get("icir")
                    passed[alpha_id][asset] = bool(od["passed"])
        return {"icir": icir, "passed": passed, "assets": list(universe)}


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def _pf_empty():
    from .factor_backtest import PortfolioMetrics
    return PortfolioMetrics()


def _ic_from_detail(detail: str) -> Optional[float]:
    """Parse 'train IC=0.0312' / 'val IC=-0.0041, ...' style gate details."""
    import re
    m = re.search(r"IC=(-?\d+\.?\d*)", detail)
    return float(m.group(1)) if m else None


def _wf_frac(od: dict[str, Any]) -> Optional[float]:
    import re
    for chk in od["checks"]:
        if chk["name"] == "walk_forward":
            m = re.search(r"frac=([\d.]+)", chk["detail"])
            if m:
                return float(m.group(1))
    return None


def _stability_frac(od: dict[str, Any]) -> Optional[float]:
    import re
    for chk in od["checks"]:
        if chk["name"] == "stability":
            m = re.search(r"consistency=([\d.]+)", chk["detail"])
            if m:
                return float(m.group(1))
    return None


def _val_consistency(train_ic: Optional[float],
                     val_ic: Optional[float]) -> float:
    """|val IC| / |train IC| when signs match, else 0."""
    if train_ic is None or val_ic is None or train_ic == 0:
        return 0.0
    if (val_ic > 0) != (train_ic > 0):
        return 0.0
    return min(1.0, abs(val_ic) / abs(train_ic))
