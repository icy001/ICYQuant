"""Alpha Cluster Analysis — de-correlate the Factor Discovery candidates on REAL data.

Motivation (post factor-real-d1): the 22 synthetic-data candidates are likely
NOT 22 independent factors — many Alpha101 formulas share the same rolling
operators and may expose the same latent market effect.  Trading all 22 would
concentrate risk instead of diversifying it.

Method (structural; the 2026 OOS segment is never touched):

1. factor values are computed for every candidate on the real daily datasets
   (``data/real/d1``) with the sealed ``FACTOR_SPEC_REAL_D1`` windows
   (rank/z = 120 bars, causal operators only);
2. pairwise **Spearman rank correlation** of the factor values is measured on
   TRAIN + VALIDATION bars only — cluster membership feeds the paper-trading
   selection, so it must not see OOS data;
3. per-asset correlations are averaged across the assets where both alphas
   are computable (>= ``MIN_OVERLAP_BARS`` overlapping bars required per
   asset; pairs never co-measurable are treated as unrelated, distance 1.0);
4. hierarchical clustering (average linkage) on distance = 1 - |corr|, cut
   so the average intra-cluster |corr| >= ``CLUSTER_ABS_CORR`` (0.80);
5. each family's **representative** is the medoid (highest mean |corr| to
   the other members); the **runner-up** is the best real-data score inside
   the family (from the factor-real-d1 report).

A secondary view correlates the **oriented positions** — the -1/0/+1 series
that actually trades, oriented by the train-IC sign exactly like the engine.
Two alphas with moderate factor correlation but near-identical positions are
still redundant in a portfolio.

Usage
-----
    python -m research.discovery.factor.cluster \
        --candidates-from research/discovery/output/factor-v1/report.json \
        --real-report research/discovery/output/factor-real-d1/report.json \
        --data-root data/real/d1
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ...data.csv_provider import CsvMarketDataProvider
from ...data.types import TimeFrame
from ..split import TimeSplit, build_split
from .evaluation import pearson, segment_ic, spearman
from .factor_backtest import orient_positions, positions_from_z, rolling_zscore
from .factor_spec import DECORRELATION_ABS_CORR, FACTOR_SPEC_REAL_D1
from .formulas import MarketData, compute_alpha
from .operators import set_rank_window

# Sealed clustering configuration ------------------------------------------------
CLUSTER_ABS_CORR = 0.80   # |corr| >= 0.80 (average linkage) -> same factor family
MIN_OVERLAP_BARS = 60     # min overlapping bars per asset for a usable correlation
SEGMENTS_USED = ("train", "validation")  # OOS never touched by the clustering
# Sensitivity thresholds reported alongside the sealed 0.80 cut, plus the
# threshold used for the recommended de-correlated paper-trading pool:
# 0.80 keeps only near-duplicates apart, 0.65 resolves the evident latent
# families (range-position reversal x2, momentum-conditioned pair).
SENSITIVITY_THRESHOLDS = (0.50, 0.60, 0.65, 0.70, 0.75, 0.80)
POOL_THRESHOLD = DECORRELATION_ABS_CORR  # sealed in factor_spec


# --------------------------------------------------------------------------- #
# Data loading & factor computation                                            #
# --------------------------------------------------------------------------- #
class _AssetCtx:
    """Everything needed per asset: bars, dates, segment indices, returns."""

    __slots__ = ("md", "dates", "used_idx", "train_idx", "bar_returns")

    def __init__(self, md: MarketData, dates: list[Any],
                 used_idx: list[int], train_idx: list[int],
                 bar_returns: list[Optional[float]]) -> None:
        self.md = md
        self.dates = dates
        self.used_idx = used_idx     # train + validation bar positions
        self.train_idx = train_idx
        self.bar_returns = bar_returns


def load_asset_contexts(data_root: Path, assets: list[str],
                        timeframe: TimeFrame = TimeFrame.D1,
                        split: Optional[TimeSplit] = None,
                        ) -> dict[str, _AssetCtx]:
    """Load OHLCV + segment indices for every asset (fail-soft per asset).

    ``split`` is the experiment's TimeSplit; defaults to the real-d1 split.
    """
    if split is None:
        split = build_split(FACTOR_SPEC_REAL_D1.split)
    provider = CsvMarketDataProvider(Path(data_root))
    ctxs: dict[str, _AssetCtx] = {}
    for asset in assets:
        try:
            bars = provider.load_bars(asset, timeframe)
        except Exception:
            continue
        if not bars:
            continue
        md = MarketData(
            open_=[b.open for b in bars],
            high=[b.high for b in bars],
            low=[b.low for b in bars],
            close=[b.close for b in bars],
            volume=[b.volume for b in bars],
        )
        dates = [b.timestamp.date() for b in bars]
        n = len(bars)
        bar_returns: list[Optional[float]] = [None] * n
        for i in range(1, n):
            if md.close[i - 1] not in (None, 0) and md.close[i] is not None:
                bar_returns[i] = md.close[i] / md.close[i - 1] - 1.0

        def _idx(seg: str) -> list[int]:
            start, end = split.spans[seg]
            return [i for i, d in enumerate(dates) if start <= d <= end]

        train_idx = _idx("train")
        val_idx = _idx("validation")
        used_idx = sorted(train_idx + val_idx)
        if not used_idx:
            continue
        ctxs[asset] = _AssetCtx(md, dates, used_idx, train_idx, bar_returns)
    return ctxs


def compute_factor_views(ctxs: dict[str, _AssetCtx], alphas: list[str],
                         z_window: int, rank_window: int,
                         ic_block_bars: int
                         ) -> tuple[dict[str, dict[str, list[Optional[float]]]],
                                    dict[str, dict[str, list[Optional[float]]]]]:
    """Factor values and oriented positions, both sliced to train+val bars.

    Returns ``(factors, positions)`` where ``factors[asset][alpha]`` is the
    raw factor series over the used bars and ``positions[asset][alpha]`` is
    the oriented -1/0/+1 series (train-IC sign, engine convention), masked
    to None during the z-score warm-up so shared leading zeros cannot
    inflate the position correlation.
    """
    set_rank_window(rank_window)
    factors: dict[str, dict[str, list[Optional[float]]]] = {}
    positions: dict[str, dict[str, list[Optional[float]]]] = {}
    for asset, ctx in ctxs.items():
        factors[asset] = {}
        positions[asset] = {}
        for alpha_id in alphas:
            try:
                f = compute_alpha(alpha_id, ctx.md)
            except Exception:
                continue
            z = rolling_zscore(f, window=z_window)
            raw_pos = positions_from_z(z)
            train_ic = segment_ic(f, ctx.bar_returns, ctx.train_idx,
                                  block_bars=ic_block_bars).ic
            pos, _orient = orient_positions(raw_pos, train_ic)
            # mask warm-up bars (z not computable) so both series start valid
            pos_masked: list[Optional[float]] = []
            for t in ctx.used_idx:
                pos_masked.append(pos[t] if z[t] is not None else None)
            factors[asset][alpha_id] = [f[t] for t in ctx.used_idx]
            positions[asset][alpha_id] = pos_masked
    return factors, positions


# --------------------------------------------------------------------------- #
# Pairwise correlation (per-asset -> averaged)                                 #
# --------------------------------------------------------------------------- #
def pairwise_correlation(series_by_asset: dict[str, dict[str, list[Optional[float]]]],
                         alphas: list[str],
                         corr_fn=spearman,
                         min_overlap: int = MIN_OVERLAP_BARS,
                         ) -> tuple[list[list[Optional[float]]], list[list[int]], list[list[int]]]:
    """Mean-across-assets correlation for every alpha pair.

    Returns ``(corr, n_assets, overlap_bars)`` as n x n matrices indexed like
    ``alphas``.  ``corr[i][j]`` is None when no asset provides enough overlap.
    """
    n = len(alphas)
    corr: list[list[Optional[float]]] = [[None] * n for _ in range(n)]
    n_assets: list[list[int]] = [[0] * n for _ in range(n)]
    overlap: list[list[int]] = [[0] * n for _ in range(n)]
    for i in range(n):
        corr[i][i] = 1.0
    for i in range(n):
        for j in range(i + 1, n):
            per_asset: list[float] = []
            bars_total = 0
            for asset in series_by_asset:
                m = series_by_asset[asset]
                if alphas[i] not in m or alphas[j] not in m:
                    continue
                xs: list[float] = []
                ys: list[float] = []
                for x, y in zip(m[alphas[i]], m[alphas[j]]):
                    if x is None or y is None or x != x or y != y:
                        continue
                    xs.append(x)
                    ys.append(y)
                if len(xs) >= min_overlap:
                    c = corr_fn(xs, ys)
                    if c is not None:
                        per_asset.append(c)
                        bars_total += len(xs)
            if per_asset:
                corr[i][j] = corr[j][i] = sum(per_asset) / len(per_asset)
                n_assets[i][j] = n_assets[j][i] = len(per_asset)
                overlap[i][j] = overlap[j][i] = bars_total
    return corr, n_assets, overlap


# --------------------------------------------------------------------------- #
# Hierarchical clustering                                                      #
# --------------------------------------------------------------------------- #
def cluster_by_correlation(alphas: list[str],
                           corr: list[list[Optional[float]]],
                           threshold: float = CLUSTER_ABS_CORR,
                           ) -> list[list[str]]:
    """Average-linkage clustering on distance = 1 - |corr|.

    Cut so that the average intra-cluster |corr| >= ``threshold``.  Pairs with
    undefined correlation (never co-measurable) sit at distance 1.0 — treated
    as unrelated.
    """
    import numpy as np
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform

    n = len(alphas)
    if n == 0:
        return []
    if n == 1:
        return [list(alphas)]
    d = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            c = corr[i][j]
            d[i, j] = 1.0 - (abs(c) if c is not None else 0.0)
    condensed = squareform(d, checks=False)
    z = linkage(condensed, method="average")
    labels = fcluster(z, t=1.0 - threshold, criterion="distance")
    groups: dict[int, list[str]] = {}
    for alpha, lab in zip(alphas, labels):
        groups.setdefault(int(lab), []).append(alpha)
    out = list(groups.values())
    for g in out:
        g.sort()
    out.sort(key=lambda g: (-len(g), g[0]))
    return out


def medoid(cluster: list[str], index: dict[str, int],
           corr: list[list[Optional[float]]]) -> tuple[str, float]:
    """Member with the highest mean |corr| to the rest of its cluster."""
    best, best_v = cluster[0], -1.0
    for a in cluster:
        vals: list[float] = []
        for b in cluster:
            if a == b:
                continue
            c = corr[index[a]][index[b]]
            vals.append(abs(c) if c is not None else 0.0)
        v = sum(vals) / len(vals) if vals else 0.0
        if v > best_v:
            best, best_v = a, v
    return best, best_v


def decorrelate(alphas: list[str],
                factors_by_asset: dict[str, dict[str, list[Optional[float]]]],
                scores: dict[str, Optional[float]],
                threshold: float = DECORRELATION_ABS_CORR,
                ) -> dict[str, Any]:
    """De-correlation Gate: one representative per correlation family.

    Pure function shared by the analysis CLI and the discovery engine:
    clusters ``alphas`` on the mean-across-assets Spearman |corr| of their
    factor values (train + validation bars only, enforced by the caller)
    and keeps, per family, the member with the highest ``scores`` value
    (ties broken alphabetically for determinism).  Correlation never sees
    the OOS segment; it only prunes redundancy among gate-passing alphas
    and never relaxes the 16-item Factor Gate.

    Returns ``{threshold, n_families, families, representatives}``.
    """
    n = len(alphas)
    if n == 0:
        return {"threshold": threshold, "n_families": 0, "families": [],
                "representatives": []}
    if n == 1:
        return {"threshold": threshold, "n_families": 1,
                "families": [{"family": "D1", "members": list(alphas),
                              "representative": alphas[0], "dropped": [],
                              "intra_mean_abs_corr": 0.0,
                              "representative_score": scores.get(alphas[0])}],
                "representatives": list(alphas)}
    corr, _, _ = pairwise_correlation(factors_by_asset, alphas)
    index = {a: i for i, a in enumerate(alphas)}
    families = cluster_by_correlation(alphas, corr, threshold)
    rows: list[dict[str, Any]] = []
    for k, members in enumerate(families, 1):
        _, intra = medoid(members, index, corr)
        best = max(members, key=lambda a: (scores.get(a) or 0.0, a))
        rows.append({
            "family": f"D{k}",
            "members": members,
            "representative": best,
            "dropped": [a for a in members if a != best],
            "intra_mean_abs_corr": round(intra, 4),
            "representative_score": scores.get(best),
        })
    return {"threshold": threshold, "n_families": len(rows), "families": rows,
            "representatives": [r["representative"] for r in rows]}


# --------------------------------------------------------------------------- #
# Report assembly                                                              #
# --------------------------------------------------------------------------- #
def _load_alpha_ids(report_path: Path, status: str = "CANDIDATE") -> list[str]:
    data = json.loads(Path(report_path).read_text(encoding="utf-8"))
    return [r["alpha_id"] for r in data.get("alpha_ranking", [])
            if r.get("status") == status]


def _load_real_perf(report_path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(Path(report_path).read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for r in data.get("alpha_ranking", []):
        out[r["alpha_id"]] = r
    return out


def build_report(alphas: list[str], factors, positions, real_perf,
                 extra_alphas: list[str],
                 extra_factors: dict[str, dict[str, list[Optional[float]]]],
                 threshold: float = CLUSTER_ABS_CORR) -> dict[str, Any]:
    index = {a: i for i, a in enumerate(alphas)}
    corr, n_assets, overlap = pairwise_correlation(factors, alphas)
    pos_corr, _, _ = pairwise_correlation(positions, alphas, corr_fn=pearson)

    clusters = cluster_by_correlation(alphas, corr, threshold)

    cluster_rows: list[dict[str, Any]] = []
    for k, members in enumerate(clusters, 1):
        rep, intra = medoid(members, index, corr)
        details = []
        for a in members:
            p = real_perf.get(a, {})
            c = corr[index[rep]][index[a]]
            details.append({
                "alpha_id": a,
                "real_score": p.get("score"),
                "real_status": p.get("status"),
                "real_assets_passed": p.get("assets_passed_count", 0),
                "real_mean_oos_ic": p.get("mean_oos_ic"),
                "real_mean_oos_icir": p.get("mean_oos_icir"),
                "real_mean_oos_sharpe": p.get("mean_oos_sharpe"),
                "abs_corr_to_representative": round(abs(c), 4) if c is not None else None,
            })
        details.sort(key=lambda d: -(d["real_score"] or 0.0))
        cluster_rows.append({
            "family": f"F{k}",
            "members": members,
            "representative": rep,
            "intra_mean_abs_corr": round(intra, 4),
            "runner_up_by_real_score": details[0]["alpha_id"] if details else None,
            "members_detail": details,
        })

    # cross-family matrix on representatives
    reps = [c["representative"] for c in cluster_rows]
    cross: dict[str, dict[str, Optional[float]]] = {}
    for a in reps:
        cross[a] = {}
        for b in reps:
            c = corr[index[a]][index[b]]
            cross[a][b] = round(abs(c), 4) if c is not None else None

    # watch-list / extra alphas: affinity to each family
    # (max over members of the mean-across-assets |corr|)
    watch_rows: list[dict[str, Any]] = []
    for w in extra_alphas:
        per_family: dict[str, float] = {}
        best_member: dict[str, str] = {}
        for k, members in enumerate(clusters, 1):
            fam_best, fam_best_member = 0.0, None
            for m in members:
                vals: list[float] = []
                for asset in factors:
                    if w not in extra_factors.get(asset, {}):
                        continue
                    if m not in factors[asset]:
                        continue
                    fa = extra_factors[asset][w]
                    fb = factors[asset][m]
                    xs = [x for x, y in zip(fa, fb)
                          if x is not None and y is not None]
                    ys = [y for x, y in zip(fa, fb)
                          if x is not None and y is not None]
                    if len(xs) >= MIN_OVERLAP_BARS:
                        c = spearman(xs, ys)
                        if c is not None:
                            vals.append(abs(c))
                if vals:
                    m_corr = sum(vals) / len(vals)
                    if m_corr > fam_best:
                        fam_best, fam_best_member = m_corr, m
            per_family[f"F{k}"] = round(fam_best, 4)
            best_member[f"F{k}"] = fam_best_member or ""
        best_family = (max(per_family, key=lambda kk: per_family[kk])
                       if per_family else None)
        p = real_perf.get(w, {})
        watch_rows.append({
            "alpha_id": w,
            "real_score": p.get("score"),
            "real_assets_passed": p.get("assets_passed_count", 0),
            "affinity_per_family": per_family,
            "best_family": best_family,
            "best_member": best_member.get(best_family or "", ""),
            "best_abs_corr": per_family.get(best_family or "", None),
        })
    watch_rows.sort(key=lambda r: -(r["real_score"] or 0.0))

    # alpha-level measurability on real data
    unmeasurable = [a for a in alphas
                    if all(n_assets[index[a]][index[b]] == 0
                           for b in alphas if b != a)]

    # threshold sensitivity: family counts + multi-member families
    sensitivity = []
    for th in SENSITIVITY_THRESHOLDS:
        cls = cluster_by_correlation(alphas, corr, th)
        sensitivity.append({
            "threshold": th,
            "n_families": len(cls),
            "multi_member": [c for c in cls if len(c) > 1],
        })

    # recommended de-correlated pool: at POOL_THRESHOLD keep one member per
    # family — the best real-data score (fallback: the medoid)
    pool = []
    for k, members in enumerate(
            cluster_by_correlation(alphas, corr, POOL_THRESHOLD), 1):
        _, intra = medoid(members, index, corr)
        scored = [(real_perf.get(a, {}).get("score") or 0.0, a)
                  for a in members]
        scored.sort(reverse=True)
        pick = scored[0][1] if scored else members[0]
        p = real_perf.get(pick, {})
        pool.append({
            "family": f"P{k}",
            "picked": pick,
            "dropped": [a for a in members if a != pick],
            "intra_mean_abs_corr": round(intra, 4),
            "picked_real_score": p.get("score"),
            "picked_real_assets_passed": p.get("assets_passed_count", 0),
            "picked_mean_oos_icir": p.get("mean_oos_icir"),
            "picked_mean_oos_sharpe": p.get("mean_oos_sharpe"),
        })

    return {
        "experiment_id": "factor-real-cluster",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": {
            "correlation": "Spearman rank correlation of factor values",
            "bars": "train + validation only (2024-01 .. 2025-12); OOS untouched",
            "aggregation": "mean of per-asset correlations (>= "
                           f"{MIN_OVERLAP_BARS} overlapping bars per asset)",
            "clustering": f"average linkage on 1-|corr|, cut at |corr| >= {threshold}",
            "representative": "medoid (max mean intra-cluster |corr|)",
            "windows": {"z_window": FACTOR_SPEC_REAL_D1.z_window,
                        "rank_window": FACTOR_SPEC_REAL_D1.rank_window},
        },
        "candidates": alphas,
        "n_candidates": len(alphas),
        "n_families": len(cluster_rows),
        "unmeasurable_on_real_data": unmeasurable,
        "clusters": cluster_rows,
        "sensitivity": sensitivity,
        "pool_threshold": POOL_THRESHOLD,
        "recommended_pool": pool,
        "cross_family_abs_corr": cross,
        "watch_affinity": watch_rows,
        "signal_corr": {a: {b: (round(corr[index[a]][index[b]], 4)
                                 if corr[index[a]][index[b]] is not None else None)
                            for b in alphas} for a in alphas},
        "position_corr": {a: {b: (round(pos_corr[index[a]][index[b]], 4)
                                   if pos_corr[index[a]][index[b]] is not None else None)
                              for b in alphas} for a in alphas},
    }


def to_markdown(data: dict[str, Any]) -> str:
    lines: list[str] = []
    w = lines.append
    w("# ICYQuant — Alpha Cluster Analysis (real data)")
    w("")
    w(f"- **Generated at**: `{data['generated_at']}`")
    w(f"- **Candidates**: {data['n_candidates']} synthetic-data factors "
      f"-> **{data['n_families']} independent families**")
    m = data["method"]
    w(f"- **Method**: {m['correlation']} on {m['bars']}; "
      f"{m['clustering']}")
    if data["unmeasurable_on_real_data"]:
        w(f"- **Unmeasurable on real data** (no co-computable asset, excluded): "
          f"{', '.join(data['unmeasurable_on_real_data'])}")
    w("")
    w("## Factor Families")
    w("")
    w("| Family | Size | Representative | Intra |corr| | Best real performer |")
    w("|---|---:|---|---:|---|")
    for c in data["clusters"]:
        best = c["members_detail"][0]
        w(f"| {c['family']} | {len(c['members'])} | {c['representative']} "
          f"| {c['intra_mean_abs_corr']:.2f} | {best['alpha_id']} "
          f"(score {best['real_score'] or 0:.4f}, "
          f"{best['real_assets_passed']} assets) |")
    w("")
    for c in data["clusters"]:
        w(f"### {c['family']} — representative `{c['representative']}` "
          f"({len(c['members'])} members)")
        w("")
        w("| Alpha | \\|corr\\| to rep | Real score | Real assets | "
          "Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |")
        w("|---|---:|---:|---:|---:|---:|---:|---|")
        for d in c["members_detail"]:
            w(f"| {d['alpha_id']} | {d['abs_corr_to_representative']} "
              f"| {d['real_score']} | {d['real_assets_passed']} "
              f"| {d['real_mean_oos_ic']} | {d['real_mean_oos_icir']} "
              f"| {d['real_mean_oos_sharpe']} | {d['real_status']} |")
        w("")
    w("## Threshold Sensitivity")
    w("")
    w("| \\|corr\\| threshold | Families | Multi-member families |")
    w("|---:|---:|---|")
    for s in data["sensitivity"]:
        mm = "; ".join("{" + ",".join(c) + "}" for c in s["multi_member"]) \
            or "—"
        w(f"| {s['threshold']:.2f} | {s['n_families']} | {mm} |")
    w("")
    w("## Recommended De-correlated Pool "
      f"(one per family at |corr| >= {data['pool_threshold']})")
    w("")
    w("| Family | Picked (best real score) | Dropped (redundant) | Intra |corr| "
      "| Real score | Real assets | Mean OOS ICIR | Mean OOS Sharpe |")
    w("|---|---|---|---:|---:|---:|---:|---:|")
    for p in data["recommended_pool"]:
        w(f"| {p['family']} | {p['picked']} "
          f"| {', '.join(p['dropped']) or '—'} | {p['intra_mean_abs_corr']:.2f} "
          f"| {p['picked_real_score']} | {p['picked_real_assets_passed']} "
          f"| {p['picked_mean_oos_icir']} | {p['picked_mean_oos_sharpe']} |")
    w("")
    w("## Cross-Family |corr| (representatives)")
    w("")
    reps = list(data["cross_family_abs_corr"].keys())
    w("|  | " + " | ".join(reps) + " |")
    w("|---|" + "---:|" * len(reps))
    for a in reps:
        cells = []
        for b in reps:
            v = data["cross_family_abs_corr"][a][b]
            cells.append("·" if v is None else f"{v:.2f}")
        w(f"| {a} | " + " | ".join(cells) + " |")
    w("")
    if data["watch_affinity"]:
        w("## Watch-list affinity (real-side strong alphas vs families)")
        w("")
        w("| Alpha | Real score | Best family | Mean |corr| to family |")
        w("|---|---:|---|---:|")
        for r in data["watch_affinity"]:
            w(f"| {r['alpha_id']} | {r['real_score']} | {r['best_family']} "
              f"| {r['best_abs_corr']} |")
        w("")
    w("---")
    w("_Clustering is structural (factor values, train+validation bars only); "
      "OOS data was never used. Representatives are medoids; families cut at "
      "|corr| >= 0.80 (average linkage)._")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m research.discovery.factor.cluster",
        description="Cluster the Factor Discovery candidates on real data.")
    parser.add_argument("--candidates-from", type=Path,
                        default=Path("research/discovery/output/factor-v1/report.json"),
                        help="Synthetic report whose CANDIDATEs are clustered.")
    parser.add_argument("--real-report", type=Path,
                        default=Path("research/discovery/output/factor-real-d1/report.json"),
                        help="Real-data report for performance context.")
    parser.add_argument("--data-root", type=Path, default=Path("data/real/d1"))
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--extra", nargs="+", default=None,
                        help="Extra alphas to profile against the families "
                             "(default: the real report's watch list + Alpha035).")
    args = parser.parse_args(argv)

    alphas = _load_alpha_ids(args.candidates_from)
    if not alphas:
        print("[cluster] no CANDIDATE alphas found in the synthetic report")
        return 1
    real_perf = _load_real_perf(args.real_report)

    extra = args.extra
    if extra is None:
        watch = []
        try:
            conv = json.loads(args.real_report.read_text(
                encoding="utf-8")).get("convergence", {})
            watch = list(conv.get("factor_watch_list", []))
        except (OSError, json.JSONDecodeError):
            pass
        extra = [a for a in watch if a not in alphas]
        if "Alpha035" not in extra and "Alpha035" not in alphas:
            extra.append("Alpha035")  # real-side strongest individual performer

    print(f"[cluster] candidates={len(alphas)} extra={extra}")
    ctxs = load_asset_contexts(args.data_root,
                               list(FACTOR_SPEC_REAL_D1.universe))
    print(f"[cluster] assets loaded: {sorted(ctxs)}")
    factors, positions = compute_factor_views(
        ctxs, alphas,
        z_window=FACTOR_SPEC_REAL_D1.z_window or 120,
        rank_window=FACTOR_SPEC_REAL_D1.rank_window or 120,
        ic_block_bars=FACTOR_SPEC_REAL_D1.ic_block_bars or 60)
    extra_factors, _ = compute_factor_views(
        ctxs, extra,
        z_window=FACTOR_SPEC_REAL_D1.z_window or 120,
        rank_window=FACTOR_SPEC_REAL_D1.rank_window or 120,
        ic_block_bars=FACTOR_SPEC_REAL_D1.ic_block_bars or 60)

    data = build_report(alphas, factors, positions, real_perf,
                        extra, extra_factors)

    out_dir = args.output_dir or (
        Path(__file__).resolve().parents[1] / "output" / "factor-real-cluster")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "report.json"
    json_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path = out_dir / "report.md"
    md_path.write_text(to_markdown(data), encoding="utf-8")

    print(f"[cluster] {data['n_candidates']} candidates -> "
          f"{data['n_families']} families")
    for c in data["clusters"]:
        print(f"[cluster]   {c['family']}: {', '.join(c['members'])} "
              f"(rep={c['representative']})")
    print(f"[cluster] report: {md_path}")
    print(f"[cluster] json:   {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
