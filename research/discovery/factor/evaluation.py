"""Information Coefficient (IC) evaluation for the Factor Discovery Track.

Definitions (per asset, per segment)
------------------------------------
- **Forward return alignment**: the factor value at bar ``t`` is paired with
  the return of bar ``t -> t+1`` (delay-1).  The last bar of a segment has no
  forward return and is dropped.
- **IC**: Pearson correlation between the aligned factor and forward-return
  series over the whole segment.
- **Rank IC**: the same correlation on Spearman ranks (average ranks for
  ties).
- **IC series / ICIR**: the segment is cut into consecutive blocks of
  ``IC_BLOCK_BARS`` aligned pairs; each block yields one IC.
  ``IC Mean = mean(blocks)``, ``IC Std = std(blocks)``,
  ``ICIR = IC Mean / IC Std``.
- **Stability**: the train segment is split into ``STABILITY_QUARTERS`` equal
  parts; the fraction of parts whose IC shares the sign of the overall train
  IC must be >= ``STABILITY_MIN_FRAC``.

All functions are pure and fail closed: not enough data -> ``None``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from .factor_spec import IC_BLOCK_BARS, IC_BLOCK_MIN_PAIRS


# --------------------------------------------------------------------------- #
# Basic statistics                                                             #
# --------------------------------------------------------------------------- #
def pearson(xs: list[float], ys: list[float]) -> Optional[float]:
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def _average_ranks(vals: list[float]) -> list[float]:
    """Spearman ranks with tie averaging (1-based)."""
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    n = len(vals)
    while i < n:
        j = i
        while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> Optional[float]:
    if len(xs) < 3:
        return None
    return pearson(_average_ranks(xs), _average_ranks(ys))


# --------------------------------------------------------------------------- #
# Alignment                                                                    #
# --------------------------------------------------------------------------- #
def align_factor_returns(factor: list[Optional[float]],
                          bar_returns: list[Optional[float]],
                          indices: list[int]) -> tuple[list[float], list[float]]:
    """Pair factor[t] with the bar return realised over t -> t+1.

    ``indices`` restricts the alignment to a segment's bar positions; a pair
    is kept only when both values exist *and* the next bar (t+1) exists with
    a computable return.
    """
    fs: list[float] = []
    rs: list[float] = []
    for t in indices:
        if t + 1 >= len(bar_returns):
            continue
        f = factor[t]
        r = bar_returns[t + 1]
        if f is None or r is None or f != f or r != r:
            continue
        fs.append(f)
        rs.append(r)
    return fs, rs


# --------------------------------------------------------------------------- #
# Segment IC report                                                            #
# --------------------------------------------------------------------------- #
@dataclass
class SegmentIC:
    """IC statistics for one (alpha, asset, segment)."""

    ic: Optional[float] = None
    rank_ic: Optional[float] = None
    ic_mean: Optional[float] = None
    ic_std: Optional[float] = None
    icir: Optional[float] = None
    block_count: int = 0
    valid_pairs: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "ic": None if self.ic is None else round(self.ic, 6),
            "rank_ic": None if self.rank_ic is None else round(self.rank_ic, 6),
            "ic_mean": None if self.ic_mean is None else round(self.ic_mean, 6),
            "ic_std": None if self.ic_std is None else round(self.ic_std, 6),
            "icir": None if self.icir is None else round(self.icir, 4),
            "block_count": self.block_count,
            "valid_pairs": self.valid_pairs,
        }


def segment_ic(factor: list[Optional[float]],
               bar_returns: list[Optional[float]],
               indices: list[int],
               block_bars: int = IC_BLOCK_BARS) -> SegmentIC:
    """Full IC statistics over a segment's bar positions."""
    fs, rs = align_factor_returns(factor, bar_returns, indices)
    out = SegmentIC(valid_pairs=len(fs))
    if len(fs) < 3:
        return out
    out.ic = pearson(fs, rs)
    out.rank_ic = spearman(fs, rs)

    ics: list[float] = []
    for start in range(0, len(fs) - IC_BLOCK_MIN_PAIRS + 1, block_bars):
        block = list(range(start, min(start + block_bars, len(fs))))
        if len(block) < IC_BLOCK_MIN_PAIRS:
            break
        ic_b = pearson([fs[i] for i in block], [rs[i] for i in block])
        if ic_b is not None:
            ics.append(ic_b)
    out.block_count = len(ics)
    if len(ics) >= 2:
        out.ic_mean = sum(ics) / len(ics)
        var = sum((x - out.ic_mean) ** 2 for x in ics) / (len(ics) - 1)
        out.ic_std = math.sqrt(var)
        if out.ic_std > 0:
            out.icir = out.ic_mean / out.ic_std
    elif len(ics) == 1:
        out.ic_mean = ics[0]
        out.ic_std = 0.0
    return out


def sign_consistency(factor: list[Optional[float]],
                     bar_returns: list[Optional[float]],
                     indices: list[int], overall_ic: Optional[float],
                     parts: int) -> Optional[float]:
    """Fraction of ``parts`` time-blocks whose IC shares the sign of
    ``overall_ic``.  Returns None when the overall IC is unavailable."""
    if overall_ic is None or overall_ic == 0 or parts < 2:
        return None
    n_pairs = sum(
        1 for t in indices
        if t + 1 < len(bar_returns)
        and factor[t] is not None and bar_returns[t + 1] is not None)
    if n_pairs < parts * 3:
        return None
    step = max(1, len(indices) // parts)
    matched = 0
    used = 0
    for p in range(parts):
        block = indices[p * step:(p + 1) * step] if p < parts - 1 \
            else indices[p * step:]
        fs, rs = align_factor_returns(factor, bar_returns, block)
        if len(fs) < 3:
            continue
        ic_p = pearson(fs, rs)
        if ic_p is None:
            continue
        used += 1
        if (ic_p > 0) == (overall_ic > 0):
            matched += 1
    if used == 0:
        return None
    return matched / used
