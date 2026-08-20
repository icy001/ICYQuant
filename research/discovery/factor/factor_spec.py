"""Sealed specification for the Factor Discovery Track (Alpha101) v1.

Mirrors the strategy line's ``spec.py``: everything that could overfit is
frozen here before the experiment runs and is never tuned afterwards.

Isolation rules (same as the strategy line):
- IC / portfolio metrics are measured separately on Train / Validation / OOS;
- walk-forward windows live inside Train + Validation only;
- the OOS segment is never used for anything except the final measurement.

Single-asset adaptations (documented deviations from the cross-sectional
originals): rank() -> rolling percentile over the past 250 bars (among the
window's available values, minimum 50% coverage — None-tolerant); scale()
-> rolling magnitude normalisation (250 bars, same None-tolerance);
IndNeutralize -> identity; vwap -> (high+low+close)/3; cap -> 20-bar
average dollar volume; all alphas are evaluated delay-1 (value at bar t
predicts the return of bar t -> t+1).  The long-short portfolio is oriented
by the sign of the train IC (train-only decision; validation / OOS never
consulted) so that direction-agnostic |IC| checks pair with a
direction-aware portfolio.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

FACTOR_SPEC_VERSION = "factor-discovery-v1"

# Signal construction -------------------------------------------------------
Z_WINDOW = 250            # rolling z-score window for the raw factor
Z_CLIP = 3.0              # z-score clip
ENTRY_Z = 1.0             # enter long/short when |z| crosses this
EXIT_Z = 0.25             # exit back to flat when |z| falls below this
IC_BLOCK_BARS = 120       # block length for the IC series (ICIR blocks)
IC_BLOCK_MIN_PAIRS = 30   # minimum valid pairs per IC block
STABILITY_QUARTERS = 4    # train segment split into this many sign blocks
STABILITY_MIN_FRAC = 0.75  # >= 3/4 quarters must share the train IC sign

# De-correlation Gate (17th gate step, applied AFTER the 16-item Factor Gate)
# ---------------------------------------------------------------------------
# Gate-passing alphas whose factor values correlate with |Spearman corr| >=
# this threshold (mean across assets, train + validation bars only) belong
# to the same latent factor family; only one representative per family is
# promoted.  0.65 resolves the evident families seen on the real daily data
# (range-position reversal A/B, momentum-conditioned pair) while 0.80 would
# keep near-duplicates together — see output/factor-real-cluster.
DECORRELATION_ABS_CORR = 0.65

# Gate thresholds (fail-closed; never tuned to let a factor through) --------
FACTOR_GATE_THRESHOLDS: dict[str, Any] = {
    "min_coverage": 0.80,        # fraction of bars with a computable factor
    "min_abs_ic": 0.02,          # |train IC| >= 0.02
    "min_abs_rank_ic": 0.02,     # |train Rank IC| >= 0.02
    "min_abs_icir": 0.30,        # |train ICIR| >= 0.30
    "min_train_sharpe": 0.50,    # train long-short Sharpe (net of cost)
    "min_val_abs_ic": 0.01,      # |validation IC| >= 0.01, same sign as train
    "min_val_return": 0.0,       # validation long-short return > 0
    "min_oos_abs_ic": 0.01,      # |OOS IC| >= 0.01, same sign as train
    "min_oos_sharpe": 0.50,      # OOS long-short Sharpe (net of cost)
    "max_drawdown": -0.50,       # OOS max drawdown floor
    "max_turnover_per_bar": 0.50,  # mean |position change| per bar
    "wf_min_positive_frac": 0.66,  # >= 2/3 walk-forward windows positive
    "min_assets_passed": 3,      # alpha must pass on >= 3 of 9 assets
    "min_block_count": 2,        # IC blocks needed for ICIR
}

# Pair-level score weights (min-max normalised, then weighted) --------------
FACTOR_SCORE_WEIGHTS: dict[str, float] = {
    "oos_icir": 0.30,
    "oos_sharpe": 0.25,
    "oos_ic": 0.15,
    "validation_consistency": 0.10,
    "stability": 0.10,
    "walk_forward_frac": 0.10,
    "turnover_penalty": -0.10,
}

# Alpha-level (cross-asset) score weights — ranking/reporting only, never
# used to relax the gate.  ``breadth`` is the fraction of the universe on
# which the alpha passes the full 16-item gate.
ALPHA_SCORE_WEIGHTS: dict[str, float] = {
    "oos_icir": 0.35,   # mean |OOS ICIR| across assets
    "oos_sharpe": 0.25,  # mean OOS long-short Sharpe across assets
    "oos_ic": 0.15,     # mean |OOS IC| across assets
    "breadth": 0.25,    # assets passed / universe size
}


@dataclass(frozen=True)
class FactorSpec:
    """Immutable Factor Discovery Track configuration."""

    version: str = FACTOR_SPEC_VERSION
    universe: tuple[str, ...] = (
        "NVDA", "SPY", "QQQ", "000688.SH", "HSTECH",
        "EURUSD", "XAUUSD", "AU", "AG",
    )
    timeframe: str = "1H"
    alphas_total: int = 101
    # signal-construction windows (bars).  None -> sealed v1 constants
    z_window: Optional[int] = None
    rank_window: Optional[int] = None
    ic_block_bars: Optional[int] = None
    # spec-style split config; None -> the strategy line's ACTIVE_SPLIT
    split: Optional[dict[str, Any]] = None
    note: str = ""
    thresholds: dict[str, Any] = field(
        default_factory=lambda: dict(FACTOR_GATE_THRESHOLDS))
    score_weights: dict[str, float] = field(
        default_factory=lambda: dict(FACTOR_SCORE_WEIGHTS))
    alpha_score_weights: dict[str, float] = field(
        default_factory=lambda: dict(ALPHA_SCORE_WEIGHTS))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "universe": list(self.universe),
            "timeframe": self.timeframe,
            "alphas_total": self.alphas_total,
            "thresholds": dict(self.thresholds),
            "score_weights": dict(self.score_weights),
            "alpha_score_weights": dict(self.alpha_score_weights),
            "note": self.note,
            "split": self.split,
            "adaptations": {
                "rank": ("rolling percentile over "
                         f"{self.rank_window or 250} bars among available "
                         "values (min 50% coverage, None-tolerant)"),
                "scale": ("rolling magnitude normalisation over "
                          f"{self.rank_window or 250} bars "
                          "(None-tolerant, min 50% coverage)"),
                "indneutralize": "identity (single-asset mode)",
                "vwap": "(high + low + close) / 3 proxy",
                "cap": "20-bar average dollar volume proxy",
                "delay": "all alphas evaluated delay-1",
                "orientation": ("long-short portfolio oriented by the sign "
                                "of the train IC (train-only decision)"),
                "z_window": self.z_window or Z_WINDOW,
                "z_clip": Z_CLIP,
                "entry_z": ENTRY_Z,
                "exit_z": EXIT_Z,
                "ic_block_bars": self.ic_block_bars or IC_BLOCK_BARS,
            },
        }


FACTOR_SPEC_V1 = FactorSpec()


# --------------------------------------------------------------------------- #
# Real-data daily variant (factor-discovery-real-d1)                           #
# --------------------------------------------------------------------------- #
# Validation of the synthetic-data candidates on REAL free daily data
# (data/real/d1, fetched by research.data.fetch_real):
#   - same 101 formulas, same 16-item Gate thresholds, same score weights;
#   - window lengths rescaled for ~640 daily bars: rank/z 250->120 bars and
#     IC blocks 120->60 bars keep roughly the same calendar span as the 1H
#     sealed spec (250 1H-bars ~ 100 days vs 120 daily-bars ~ 170 days);
#   - split follows the real dataset range (2024-01 .. 2026-08):
#     train 18m / validation 6m / oos ~7.5m — OOS still never touched
#     before the final measurement.
# Known data limitations (recorded in data/real/d1/manifest.json): AU/AG
# dominant-continuous futures are not roll-adjusted; EURUSD is a BOC cross
# rate with pseudo-OHLC; XAUUSD is proxied by COMEX GC.
FACTOR_SPEC_REAL_D1 = FactorSpec(
    version="factor-discovery-real-d1",
    timeframe="1D",
    z_window=120,
    rank_window=120,
    ic_block_bars=60,
    split={
        "name": "real-2y-60-20-20",
        "train": {"start": "2024-01-01", "end": "2025-06-30"},
        "validation": {"start": "2025-07-01", "end": "2025-12-31"},
        "oos": {"start": "2026-01-01", "end": "2026-08-19"},
        "note": ("Real free daily data (akshare): train 18m / val 6m / "
                 "oos ~7.5m; AU/AG not roll-adjusted, EURUSD BOC cross "
                 "rate, XAUUSD proxied by COMEX GC."),
    },
    note=("Real-data validation of the factor-discovery-v1 candidates; "
          "identical Gate thresholds, windows rescaled for daily bars."),
)
