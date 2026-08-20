"""Time-series operators for the WorldQuant Alpha101 factor library.

Single-asset adaptation (documented, sealed in ``factor_spec``)
----------------------------------------------------------------
The original Alpha101 operators are defined over a *cross-section* of stocks
on each day.  The Factor Discovery Track evaluates every alpha on a *single
asset* as a time series, so the cross-sectional operators are adapted:

- ``rank(x)`` (cross-sectional percentile) becomes a **rolling percentile**
  of the current value over the past ``RANK_WINDOW`` bars (including the
  current bar).  This preserves the operator's purpose — mapping arbitrary
  scales to a comparable [0, 1] signal — while staying causal.  The
  adaptation is None-tolerant (percentile among the window's available
  values, minimum 50% coverage) so nested operators with occasional
  degenerate windows remain computable.
- ``scale(x)`` (cross-sectional unit booksize) becomes a rolling magnitude
  normalisation: ``x_t / mean(|x|, RANK_WINDOW)`` with the same
  None-tolerance.
- ``IndNeutralize(x, ...)`` becomes the **identity** — there is no industry
  classification for a single instrument.
- ``cap`` is proxied by the 20-bar average dollar volume.

All operators are strictly causal: the output at bar ``t`` depends only on
input values at bars ``<= t``.  Warm-up / not-computable values are ``None``;
any ``None`` inside a rolling window propagates to ``None`` output.

Performance: rolling sums/correlations are incremental (O(n)); rolling
percentiles and min/max use sorted windows or monotonic deques.
"""
from __future__ import annotations

import math
from bisect import bisect_left, bisect_right, insort
from collections import deque
from typing import Optional

Number = Optional[float]
Series = list[Number]

# Rolling window used for the rank()/scale() cross-sectional adaptations.
# Configurable at runtime via set_rank_window() so experiments on different
# frequencies (e.g. daily data with ~640 bars) can use a shorter window
# without touching the sealed 1H default of 250.
RANK_WINDOW = 250


def set_rank_window(n: int) -> None:
    """Set the rolling window for rank()/scale() (call before computing)."""
    global RANK_WINDOW
    RANK_WINDOW = max(2, int(round(n)))


# --------------------------------------------------------------------------- #
# Element-wise unary                                                          #
# --------------------------------------------------------------------------- #
def sign(x: Series) -> Series:
    out: Series = []
    for v in x:
        if v is None or v != v:
            out.append(None)
        elif v > 0:
            out.append(1.0)
        elif v < 0:
            out.append(-1.0)
        else:
            out.append(0.0)
    return out


def abs_(x: Series) -> Series:
    return [None if v is None else abs(v) for v in x]


def log_(x: Series) -> Series:
    out: Series = []
    for v in x:
        if v is None or v <= 0:
            out.append(None)
        else:
            out.append(math.log(v))
    return out


def power(x: Series, e: float) -> Series:
    out: Series = []
    for v in x:
        if v is None:
            out.append(None)
        else:
            try:
                out.append(math.pow(v, e))
            except (OverflowError, ValueError):
                out.append(None)
    return out


def signed_power(x: Series, e) -> Series:
    """x^e element-wise; ``e`` may be a constant or a Series.

    Returns ``sign(x) * |x| ** e`` (WorldQuant definition).  |x| == 0 with a
    negative exponent is not computable -> None.  Results are clipped to a
    sane magnitude to keep downstream arithmetic finite.
    """
    es = e if isinstance(e, list) else None
    const_e = None if es is not None else float(e)
    out: Series = []
    for i, v in enumerate(x):
        ev = es[i] if es is not None else const_e
        if v is None or ev is None:
            out.append(None)
            continue
        a = abs(v)
        if a == 0.0 and ev < 0:
            out.append(None)
            continue
        try:
            r = math.copysign(a ** ev, v) if a > 0 else (0.0 if ev >= 0 else None)
        except (OverflowError, ZeroDivisionError):
            out.append(None)
            continue
        if r is not None and (r != r or abs(r) > 1e12):
            out.append(None if r != r else math.copysign(1e12, r))
        else:
            out.append(r)
    return out


# --------------------------------------------------------------------------- #
# Element-wise binary (None / NaN propagate; scalars allowed)                  #
# --------------------------------------------------------------------------- #
def _binop(a, b, fn) -> Series:
    as_list = isinstance(a, list)
    bs_list = isinstance(b, list)
    n = len(a) if as_list else len(b)
    out: Series = []
    for i in range(n):
        va = a[i] if as_list else a
        vb = b[i] if bs_list else b
        if va is None or vb is None or va != va or vb != vb:
            out.append(None)
        else:
            r = fn(va, vb)
            out.append(None if r != r else r)
    return out


def add(a, b) -> Series:
    return _binop(a, b, lambda x, y: x + y)


def sub(a, b) -> Series:
    return _binop(a, b, lambda x, y: x - y)


def mul(a, b) -> Series:
    return _binop(a, b, lambda x, y: x * y)


def div(a, b) -> Series:
    def _d(x, y):
        if y == 0:
            return None  # undefined at this bar (fail-closed, not a crash)
        return x / y
    return _binop(a, b, _d)


def min_(a, b) -> Series:
    return _binop(a, b, min)


def max_(a, b) -> Series:
    return _binop(a, b, max)


def lt(a, b) -> list[Optional[bool]]:
    return _cmp(a, b, lambda x, y: x < y)


def gt(a, b) -> list[Optional[bool]]:
    return _cmp(a, b, lambda x, y: x > y)


def le(a, b) -> list[Optional[bool]]:
    return _cmp(a, b, lambda x, y: x <= y)


def ge(a, b) -> list[Optional[bool]]:
    return _cmp(a, b, lambda x, y: x >= y)


def _cmp(a, b, fn) -> list[Optional[bool]]:
    as_list = isinstance(a, list)
    bs_list = isinstance(b, list)
    n = len(a) if as_list else len(b)
    out: list[Optional[bool]] = []
    for i in range(n):
        va = a[i] if as_list else a
        vb = b[i] if bs_list else b
        if va is None or vb is None or va != va or vb != vb:
            out.append(None)
        else:
            out.append(fn(va, vb))
    return out


def where(cond: list[Optional[bool]], a, b) -> Series:
    """Element-wise ``cond ? a : b``; ``a``/``b`` may be Series or scalar."""
    as_list = isinstance(a, list)
    bs_list = isinstance(b, list)
    n = len(cond)
    out: Series = []
    for i in range(n):
        c = cond[i]
        if c is None:
            out.append(None)
            continue
        va = a[i] if as_list else a
        vb = b[i] if bs_list else b
        v = va if c else vb
        if v is None or v != v:
            out.append(None)
        else:
            out.append(float(v))
    return out


def or_(*conds) -> list[Optional[bool]]:
    """Element-wise logical OR over boolean series."""
    n = len(conds[0])
    out: list[Optional[bool]] = []
    for i in range(n):
        vals = [c[i] for c in conds]
        if any(v is None for v in vals):
            out.append(None)
        else:
            out.append(any(vals))
    return out


# --------------------------------------------------------------------------- #
# Rolling core (incremental sums with None-propagation)                        #
# --------------------------------------------------------------------------- #
class _RollingStats:
    """Rolling window of (x, y) pairs with incremental sums.

    Tracks sums of x, y, x*y, x*x, y*y over the last ``d`` bars.  Windows
    containing one or more None values yield None outputs.  Sums are
    recomputed from scratch whenever the window transitions between the
    "clean" and "dirty" (contains None) state.
    """

    __slots__ = ("d", "xq", "yq", "none_count", "sx", "sy", "sxy", "sxx",
                 "syy", "dirty")

    def __init__(self, d: int) -> None:
        self.d = d
        self.xq: deque = deque()
        self.yq: deque = deque()
        self.none_count = 0
        self.sx = self.sy = self.sxy = self.sxx = self.syy = 0.0
        self.dirty = False

    def push(self, x: Number, y: Number) -> None:
        if len(self.xq) == self.d:
            ox = self.xq.popleft()
            oy = self.yq.popleft()
            if ox is None or oy is None:
                self.none_count -= 1
            else:
                self.sx -= ox
                self.sy -= oy
                self.sxy -= ox * oy
                self.sxx -= ox * ox
                self.syy -= oy * oy
        self.xq.append(x)
        self.yq.append(y)
        if x is None or y is None:
            self.none_count += 1
        else:
            self.sx += x
            self.sy += y
            self.sxy += x * y
            self.sxx += x * x
            self.syy += y * y

    @property
    def ready(self) -> bool:
        return len(self.xq) == self.d and self.none_count == 0

    def recompute_if_dirty(self) -> None:
        if self.none_count == 0 and self.dirty:
            self.sx = sum(self.xq)
            self.sy = sum(self.yq)
            self.sxy = sum(x * y for x, y in zip(self.xq, self.yq))
            self.sxx = sum(x * x for x in self.xq)
            self.syy = sum(y * y for y in self.yq)
            self.dirty = False
        elif self.none_count > 0:
            self.dirty = True

    def correlation(self) -> Number:
        self.recompute_if_dirty()
        if not self.ready:
            return None
        d = float(self.d)
        num = d * self.sxy - self.sx * self.sy
        den_x = d * self.sxx - self.sx * self.sx
        den_y = d * self.syy - self.sy * self.sy
        if den_x <= 0 or den_y <= 0:
            return None
        return num / math.sqrt(den_x * den_y)

    def covariance(self) -> Number:
        self.recompute_if_dirty()
        if not self.ready:
            return None
        d = float(self.d)
        return (d * self.sxy - self.sx * self.sy) / (d * d)

    def mean_x(self) -> Number:
        self.recompute_if_dirty()
        if not self.ready:
            return None
        return self.sx / self.d

    def mean_y(self) -> Number:
        self.recompute_if_dirty()
        if not self.ready:
            return None
        return self.sy / self.d

    def sum_x(self) -> Number:
        self.recompute_if_dirty()
        if not self.ready:
            return None
        return self.sx

    def std_x(self) -> Number:
        """Population standard deviation of x over the window."""
        self.recompute_if_dirty()
        if not self.ready:
            return None
        d = float(self.d)
        var = self.sxx / d - (self.sx / d) ** 2
        if var < 0:
            var = 0.0
        return math.sqrt(var)


def correlation(x: Series, y: Series, d: int) -> Series:
    d = max(1, int(round(d)))
    st = _RollingStats(d)
    out: Series = []
    for xv, yv in zip(x, y):
        st.push(xv, yv)
        out.append(st.correlation())
    return out


def covariance(x: Series, y: Series, d: int) -> Series:
    d = max(1, int(round(d)))
    st = _RollingStats(d)
    out: Series = []
    for xv, yv in zip(x, y):
        st.push(xv, yv)
        out.append(st.covariance())
    return out


def ts_sum(x: Series, d: int) -> Series:
    d = max(1, int(round(d)))
    st = _RollingStats(d)
    out: Series = []
    for xv in x:
        st.push(xv, 0.0)
        out.append(st.sum_x())
    return out


def ts_mean(x: Series, d: int) -> Series:
    d = max(1, int(round(d)))
    st = _RollingStats(d)
    out: Series = []
    for xv in x:
        st.push(xv, 0.0)
        out.append(st.mean_x())
    return out


def stddev(x: Series, d: int) -> Series:
    d = max(1, int(round(d)))
    st = _RollingStats(d)
    out: Series = []
    for xv in x:
        st.push(xv, 0.0)
        out.append(st.std_x())
    return out


# --------------------------------------------------------------------------- #
# Delay / delta                                                                #
# --------------------------------------------------------------------------- #
def delay(x: Series, d: int) -> Series:
    d = max(1, int(round(d)))
    if d >= len(x):
        return [None] * len(x)
    return [None] * d + list(x[:-d])


def delta(x: Series, d: int) -> Series:
    dl = delay(x, d)
    return [None if (v is None or w is None) else v - w
            for v, w in zip(x, dl)]


# --------------------------------------------------------------------------- #
# Rolling min / max / argmin / argmax (monotonic deques)                       #
# --------------------------------------------------------------------------- #
def ts_min(x: Series, d: int) -> Series:
    return _rolling_extreme(x, d, want_max=False, want_arg=False)


def ts_max(x: Series, d: int) -> Series:
    return _rolling_extreme(x, d, want_max=True, want_arg=False)


def ts_argmin(x: Series, d: int) -> Series:
    """0-based offset of the window minimum counted from the newest bar
    (0 = the current bar holds the minimum, d-1 = the oldest bar)."""
    return _rolling_extreme(x, d, want_max=False, want_arg=True)


def ts_argmax(x: Series, d: int) -> Series:
    """0-based offset of the window maximum counted from the newest bar."""
    return _rolling_extreme(x, d, want_max=True, want_arg=True)


def _rolling_extreme(x: Series, d: int, want_max: bool,
                     want_arg: bool) -> Series:
    d = max(1, int(round(d)))
    n = len(x)
    out: Series = [None] * n
    # dq holds (index, value) with values kept monotonic; window tracks raw
    # values so we can count Nones entering/leaving the window.
    dq: deque = deque()
    window: deque = deque()
    none_in_window = 0
    for i in range(n):
        v = x[i]
        window.append(v)
        if v is None:
            none_in_window += 1
        else:
            while dq:
                dv = dq[-1][1]
                if (dv < v) if want_max else (dv > v):
                    dq.pop()
                else:
                    break
            dq.append((i, v))
        if len(window) > d:
            old = window.popleft()
            if old is None:
                none_in_window -= 1
        # evict indices that fell out of the window
        while dq and dq[0][0] <= i - d:
            dq.popleft()
        if i >= d - 1 and none_in_window == 0 and dq:
            idx, dv = dq[0]
            out[i] = float(i - idx) if want_arg else dv
    return out


# --------------------------------------------------------------------------- #
# Rolling percentile (ts_rank and the rank() adaptation)                       #
# --------------------------------------------------------------------------- #
def ts_rank(x: Series, d: int) -> Series:
    """Percentile of the current value within the past ``d`` values
    (window includes the current bar; ties get the average percentile)."""
    d = max(2, int(round(d)))
    n = len(x)
    out: Series = [None] * n
    window: deque = deque()
    sorted_w: list[float] = []
    for i in range(n):
        v = x[i]
        window.append(v)
        if v is not None:
            insort(sorted_w, v)
        if len(window) > d:
            old = window.popleft()
            if old is not None:
                pos = bisect_left(sorted_w, old)
                sorted_w.pop(pos)
        if i >= d - 1 and v is not None and len(sorted_w) == d:
            lo = bisect_left(sorted_w, v)
            hi = bisect_right(sorted_w, v)
            out[i] = ((lo + hi) / 2.0) / d
    return out


def rank(x: Series, window: Optional[int] = None,
         min_valid_frac: float = 0.5) -> Series:
    """Single-asset adaptation of the cross-sectional ``rank`` operator:
    rolling percentile of the current value over the past ``window`` bars.

    Unlike the strict :func:`ts_rank` (paper operator), the adaptation is
    **None-tolerant**: the percentile is taken among the *available* values
    in the window, as long as at least ``min_valid_frac`` of the window is
    computable.  This keeps ``rank()`` usable on sparse series (e.g. nested
    correlation chains whose windows occasionally degenerate to zero
    variance) while staying causal.
    """
    d = max(2, int(round(window if window is not None else RANK_WINDOW)))
    min_valid = max(2, int(d * min_valid_frac))
    n = len(x)
    out: Series = [None] * n
    window_q: deque = deque()
    sorted_w: list[float] = []
    for i in range(n):
        v = x[i]
        window_q.append(v)
        if v is not None:
            insort(sorted_w, v)
        if len(window_q) > d:
            old = window_q.popleft()
            if old is not None:
                pos = bisect_left(sorted_w, old)
                sorted_w.pop(pos)
        if i >= d - 1 and v is not None and len(sorted_w) >= min_valid:
            lo = bisect_left(sorted_w, v)
            hi = bisect_right(sorted_w, v)
            out[i] = ((lo + hi) / 2.0) / len(sorted_w)
    return out


def scale(x: Series, window: Optional[int] = None, a: float = 1.0,
          min_valid_frac: float = 0.5) -> Series:
    """Single-asset adaptation of the cross-sectional ``scale`` operator:
    ``x_t * a / mean(|x|, window)`` — normalises magnitude to the rolling
    average absolute value while preserving sign.

    None-tolerant like :func:`rank`: the mean runs over the window's
    available values with a ``min_valid_frac`` coverage floor.
    """
    d = max(1, int(round(window if window is not None else RANK_WINDOW)))
    min_valid = max(1, int(d * min_valid_frac))
    n = len(x)
    out: Series = [None] * n
    window_q: deque = deque()
    s = 0.0
    count = 0
    for i in range(n):
        v = x[i]
        window_q.append(v)
        if v is not None:
            s += abs(v)
            count += 1
        if len(window_q) > d:
            old = window_q.popleft()
            if old is not None:
                s -= abs(old)
                count -= 1
        if i >= d - 1 and v is not None and count >= min_valid and s > 0:
            out[i] = v * a / (s / count)
    return out


# --------------------------------------------------------------------------- #
# Decay / product                                                              #
# --------------------------------------------------------------------------- #
def decay_linear(x: Series, d: int) -> Series:
    """Linearly decaying weighted average: weights d, d-1, ..., 1 from the
    oldest to the newest bar, normalised to sum to 1."""
    d = max(1, int(round(d)))
    if d == 1:
        return list(x)
    n = len(x)
    out: Series = [None] * n
    wsum = d * (d + 1) / 2.0
    for i in range(d - 1, n):
        acc = 0.0
        ok = True
        for j in range(d):
            v = x[i - d + 1 + j]
            if v is None:
                ok = False
                break
            acc += (j + 1) * v
        out[i] = acc / wsum if ok else None
    return out


def product(x: Series, d: int) -> Series:
    """Rolling product over the past ``d`` bars."""
    d = max(1, int(round(d)))
    if d == 1:
        return list(x)
    n = len(x)
    out: Series = [None] * n
    for i in range(d - 1, n):
        acc = 1.0
        ok = True
        for j in range(i - d + 1, i + 1):
            v = x[j]
            if v is None:
                ok = False
                break
            acc *= v
            if acc != acc or abs(acc) > 1e150:
                ok = False
                break
        out[i] = acc if ok else None
    return out
