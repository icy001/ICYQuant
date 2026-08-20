"""WorldQuant 101 Formulaic Alphas — faithful single-asset transcription.

Source: Zura Kakushadze, "101 Formulaic Alphas" (arXiv:1601.00991, 2015).
The formulas below follow the paper's Appendix A verbatim, with these sealed
single-asset adaptations (see ``operators.py`` and ``factor_spec.py``):

- ``rank(x)``       -> rolling percentile over the past 250 bars
- ``scale(x)``      -> rolling magnitude normalisation over 250 bars
- ``IndNeutralize`` -> identity (no industry classification)
- ``vwap``          -> (high + low + close) / 3 proxy
- ``cap``           -> 20-bar average dollar volume proxy
- ``adv{d}``        -> rolling d-bar mean of dollar volume (close * volume)
- fractional window lengths (e.g. 16.1219) are rounded to integers
- every alpha is evaluated delay-1: the value at bar t may only predict the
  return over bar t -> t+1 (never the bar it was computed on)

Each formula returns ``Series`` (list of Optional[float]); ``None`` marks
warm-up / not-computable bars.
"""
from __future__ import annotations

from typing import Callable

from .operators import (
    Number,
    Series,
    abs_,
    add,
    correlation,
    covariance,
    decay_linear,
    delay,
    delta,
    div,
    ge,
    gt,
    le,
    log_,
    lt,
    max_,
    min_,
    mul,
    or_,
    power,
    product,
    rank,
    scale,
    sign,
    signed_power,
    stddev,
    sub,
    ts_argmax,
    ts_argmin,
    ts_max,
    ts_mean,
    ts_min,
    ts_rank,
    ts_sum,
    where,
)

# Decimal windows in the paper are rounded: W(16.1219) == 16.
W = lambda x: max(1, int(round(x)))


class MarketData:
    """OHLCV context for one asset with cached derived series."""

    __slots__ = ("open", "high", "low", "close", "volume", "vwap",
                 "returns", "_adv")

    def __init__(self, open_: Series, high: Series, low: Series,
                 close: Series, volume: Series) -> None:
        self.open = open_
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        # vwap proxy: (high + low + close) / 3
        self.vwap: Series = [None if (h is None or l is None or c is None)
                             else (h + l + c) / 3.0
                             for h, l, c in zip(high, low, close)]
        # close-to-close returns
        self.returns: Series = [None] * len(close)
        for i in range(1, len(close)):
            if close[i] is not None and close[i - 1] is not None \
                    and close[i - 1] != 0:
                self.returns[i] = close[i] / close[i - 1] - 1.0
        self._adv: dict[int, Series] = {}

    def adv(self, d: int) -> Series:
        """Average daily dollar volume over the past ``d`` bars."""
        d = max(1, int(round(d)))
        if d not in self._adv:
            dollar = mul(self.close, self.volume)
            self._adv[d] = ts_mean(dollar, d)
        return self._adv[d]

    @property
    def cap(self) -> Series:
        """Market cap proxy: 20-bar average dollar volume."""
        return self.adv(20)


AlphaFn = Callable[[MarketData], Series]


# --------------------------------------------------------------------------- #
# Alpha#1 .. Alpha#101                                                         #
# --------------------------------------------------------------------------- #
def alpha_001(md: MarketData) -> Series:
    # (rank(Ts_ArgMax(SignedPower(((returns < 0) ? stddev(returns, 20) : close), 2.), 5)) - 0.5)
    inner = signed_power(
        where(lt(md.returns, 0.0), stddev(md.returns, 20), md.close), 2.0)
    return sub(rank(ts_argmax(inner, 5)), [0.5] * len(inner))


def alpha_002(md: MarketData) -> Series:
    # (-1 * correlation(rank(delta(log(volume), 2)), rank(((close - open) / open)), 6))
    return mul(-1, correlation(
        rank(delta(log_(md.volume), 2)),
        rank(div(sub(md.close, md.open), md.open)), 6))


def alpha_003(md: MarketData) -> Series:
    # (-1 * correlation(rank(open), rank(volume), 10))
    return mul(-1, correlation(rank(md.open), rank(md.volume), 10))


def alpha_004(md: MarketData) -> Series:
    # (-1 * Ts_Rank(rank(low), 9))
    return mul(-1, ts_rank(rank(md.low), 9))


def alpha_005(md: MarketData) -> Series:
    # (rank((open - (sum(vwap, 10) / 10))) * (-1 * abs(rank((close - vwap)))))
    return mul(
        rank(sub(md.open, div(ts_sum(md.vwap, 10), 10))),
        mul(-1, abs_(rank(sub(md.close, md.vwap)))))


def alpha_006(md: MarketData) -> Series:
    # (-1 * correlation(open, volume, 10))
    return mul(-1, correlation(md.open, md.volume, 10))


def alpha_007(md: MarketData) -> Series:
    # ((adv20 < volume) ? ((-1 * ts_rank(abs(delta(close, 7)), 60)) * sign(delta(close, 7))) : (-1 * 1))
    return where(
        lt(md.adv(20), md.volume),
        mul(mul(-1, ts_rank(abs_(delta(md.close, 7)), 60)),
            sign(delta(md.close, 7))),
        -1.0)


def alpha_008(md: MarketData) -> Series:
    # (-1 * rank(((sum(open, 5) * sum(returns, 5)) - delay((sum(open, 5) * sum(returns, 5)), 10))))
    p = mul(ts_sum(md.open, 5), ts_sum(md.returns, 5))
    return mul(-1, rank(sub(p, delay(p, 10))))


def _alpha_9_10_inner(md: MarketData, d: int) -> Series:
    # ((0 < ts_min(delta(close, 1), d)) ? delta(close, 1)
    #  : ((ts_max(delta(close, 1), d) < 0) ? delta(close, 1) : (-1 * delta(close, 1))))
    dc = delta(md.close, 1)
    return where(
        gt(ts_min(dc, d), 0.0), dc,
        where(lt(ts_max(dc, d), 0.0), dc, mul(-1, dc)))


def alpha_009(md: MarketData) -> Series:
    return _alpha_9_10_inner(md, 5)


def alpha_010(md: MarketData) -> Series:
    return rank(_alpha_9_10_inner(md, 4))


def alpha_011(md: MarketData) -> Series:
    # ((rank(ts_max((vwap - close), 3)) + rank(ts_min((vwap - close), 3))) * rank(delta(volume, 3)))
    vc = sub(md.vwap, md.close)
    return mul(add(rank(ts_max(vc, 3)), rank(ts_min(vc, 3))),
               rank(delta(md.volume, 3)))


def alpha_012(md: MarketData) -> Series:
    # (sign(delta(volume, 1)) * (-1 * delta(close, 1)))
    return mul(sign(delta(md.volume, 1)), mul(-1, delta(md.close, 1)))


def alpha_013(md: MarketData) -> Series:
    # (-1 * rank(covariance(rank(close), rank(volume), 5)))
    return mul(-1, rank(covariance(rank(md.close), rank(md.volume), 5)))


def alpha_014(md: MarketData) -> Series:
    # ((-1 * rank(delta(returns, 3))) * correlation(open, volume, 10))
    return mul(mul(-1, rank(delta(md.returns, 3))),
               correlation(md.open, md.volume, 10))


def alpha_015(md: MarketData) -> Series:
    # (-1 * sum(rank(correlation(rank(high), rank(volume), 3)), 3))
    return mul(-1, ts_sum(
        rank(correlation(rank(md.high), rank(md.volume), 3)), 3))


def alpha_016(md: MarketData) -> Series:
    # (-1 * rank(covariance(rank(high), rank(volume), 5)))
    return mul(-1, rank(covariance(rank(md.high), rank(md.volume), 5)))


def alpha_017(md: MarketData) -> Series:
    # (((-1 * rank(ts_rank(close, 10))) * rank(delta(delta(close, 1), 1))) * rank(ts_rank((volume / adv20), 5)))
    return mul(
        mul(mul(-1, rank(ts_rank(md.close, 10))),
            rank(delta(delta(md.close, 1), 1))),
        rank(ts_rank(div(md.volume, md.adv(20)), 5)))


def alpha_018(md: MarketData) -> Series:
    # (-1 * rank(((stddev(abs((close - open)), 5) + (close - open)) + correlation(close, open, 10))))
    co = sub(md.close, md.open)
    return mul(-1, rank(add(add(stddev(abs_(co), 5), co),
                            correlation(md.close, md.open, 10))))


def alpha_019(md: MarketData) -> Series:
    # ((-1 * sign(((close - delay(close, 7)) + delta(close, 7)))) * (1 + rank((1 + sum(returns, 250)))))
    return mul(
        mul(-1, sign(add(sub(md.close, delay(md.close, 7)),
                         delta(md.close, 7)))),
        add(1.0, rank(add(1.0, ts_sum(md.returns, 250)))))


def alpha_020(md: MarketData) -> Series:
    # (((-1 * rank((open - delay(high, 1)))) * rank((open - delay(close, 1)))) * rank((open - delay(low, 1))))
    return mul(
        mul(mul(-1, rank(sub(md.open, delay(md.high, 1)))),
            rank(sub(md.open, delay(md.close, 1)))),
        rank(sub(md.open, delay(md.low, 1))))


def alpha_021(md: MarketData) -> Series:
    # ((((sum(close, 8) / 8) + stddev(close, 8)) < (sum(close, 2) / 2)) ? (-1 * 1)
    #  : (((sum(close, 2) / 2) < ((sum(close, 8) / 8) - stddev(close, 8))) ? 1
    #  : (((1 < (volume / adv20)) || ((volume / adv20) == 1)) ? 1 : (-1 * 1))))
    s8 = div(ts_sum(md.close, 8), 8)
    s2 = div(ts_sum(md.close, 2), 2)
    sd8 = stddev(md.close, 8)
    va = div(md.volume, md.adv(20))
    return where(
        lt(add(s8, sd8), s2), -1.0,
        where(lt(s2, sub(s8, sd8)), 1.0,
              where(ge(va, 1.0), 1.0, -1.0)))


def alpha_022(md: MarketData) -> Series:
    # (-1 * (delta(correlation(high, volume, 5), 5) * rank(stddev(close, 20))))
    return mul(-1, mul(delta(correlation(md.high, md.volume, 5), 5),
                       rank(stddev(md.close, 20))))


def alpha_023(md: MarketData) -> Series:
    # (((sum(high, 20) / 20) < high) ? (-1 * delta(high, 2)) : 0)
    return where(lt(div(ts_sum(md.high, 20), 20), md.high),
                 mul(-1, delta(md.high, 2)), 0.0)


def alpha_024(md: MarketData) -> Series:
    # ((((delta((sum(close, 100) / 100), 100) / delay(close, 100)) < 0.05)
    #   || ((delta((sum(close, 100) / 100), 100) / delay(close, 100)) == 0.05))
    #  ? (-1 * (close - ts_min(close, 100))) : (-1 * delta(close, 3)))
    sma100 = div(ts_sum(md.close, 100), 100)
    q = div(delta(sma100, 100), delay(md.close, 100))
    return where(le(q, 0.05),
                 mul(-1, sub(md.close, ts_min(md.close, 100))),
                 mul(-1, delta(md.close, 3)))


def alpha_025(md: MarketData) -> Series:
    # rank(((((-1 * returns) * adv20) * vwap) * (high - close)))
    return rank(mul(
        mul(mul(mul(-1, md.returns), md.adv(20)), md.vwap),
        sub(md.high, md.close)))


def alpha_026(md: MarketData) -> Series:
    # (-1 * ts_max(correlation(ts_rank(volume, 5), ts_rank(high, 5), 5), 3))
    return mul(-1, ts_max(
        correlation(ts_rank(md.volume, 5), ts_rank(md.high, 5), 5), 3))


def alpha_027(md: MarketData) -> Series:
    # ((0.5 < rank((sum(correlation(rank(volume), rank(vwap), 6), 2) / 2.0))) ? (-1 * 1) : 1)
    q = div(ts_sum(correlation(rank(md.volume), rank(md.vwap), 6), 2), 2.0)
    return where(gt(rank(q), 0.5), -1.0, 1.0)


def alpha_028(md: MarketData) -> Series:
    # scale(((correlation(adv20, low, 5) + ((high + low) / 2)) - close))
    return scale(sub(
        add(correlation(md.adv(20), md.low, 5),
            div(add(md.high, md.low), 2.0)),
        md.close))


def alpha_029(md: MarketData) -> Series:
    # (min(product(rank(rank(scale(log(sum(ts_min(rank(rank((-1 * rank(delta((close - 1), 5))))), 2), 1))))), 1), 5)
    # + ts_rank(delay((-1 * returns), 6), 5))
    inner = rank(rank(scale(log_(ts_sum(
        ts_min(rank(rank(mul(-1, rank(delta(sub(md.close, [1.0] * len(md.close)), 5))))), 2), 1)))))
    return add(min_(product(inner, 1), 5.0),
               ts_rank(delay(mul(-1, md.returns), 6), 5))


def alpha_030(md: MarketData) -> Series:
    # (((1.0 - rank(((sign((close - delay(close, 1))) + sign((delay(close, 1) - delay(close, 2))))
    #   + sign((delay(close, 2) - delay(close, 3)))))) * sum(volume, 5)) / sum(volume, 20))
    s = add(
        add(sign(sub(md.close, delay(md.close, 1))),
            sign(sub(delay(md.close, 1), delay(md.close, 2)))),
        sign(sub(delay(md.close, 2), delay(md.close, 3))))
    return div(mul(sub(1.0, rank(s)), ts_sum(md.volume, 5)),
               ts_sum(md.volume, 20))


def alpha_031(md: MarketData) -> Series:
    # ((rank(rank(rank(decay_linear((-1 * rank(rank(delta(close, 10)))), 10))))
    #  + rank((-1 * delta(close, 3)))) + sign(scale(correlation(adv20, low, 12))))
    return add(
        add(rank(rank(rank(decay_linear(
            mul(-1, rank(rank(delta(md.close, 10)))), 10)))),
            rank(mul(-1, delta(md.close, 3)))),
        sign(scale(correlation(md.adv(20), md.low, 12))))


def alpha_032(md: MarketData) -> Series:
    # (scale(((sum(close, 7) / 7) - close)) + (20 * scale(correlation(vwap, delay(close, 5), 230))))
    return add(scale(sub(div(ts_sum(md.close, 7), 7), md.close)),
               mul(20, scale(correlation(md.vwap, delay(md.close, 5), 230))))


def alpha_033(md: MarketData) -> Series:
    # rank((-1 * ((1 - (open / close))^1)))
    return rank(mul(-1, power(sub(1.0, div(md.open, md.close)), 1)))


def alpha_034(md: MarketData) -> Series:
    # rank(((1 - rank((stddev(returns, 2) / stddev(returns, 5)))) + (1 - rank(delta(close, 1)))))
    return rank(add(
        sub(1.0, rank(div(stddev(md.returns, 2), stddev(md.returns, 5)))),
        sub(1.0, rank(delta(md.close, 1)))))


def alpha_035(md: MarketData) -> Series:
    # ((Ts_Rank(volume, 32) * (1 - Ts_Rank(((close + high) - low), 16))) * (1 - Ts_Rank(returns, 32)))
    return mul(
        mul(ts_rank(md.volume, 32),
            sub(1.0, ts_rank(sub(add(md.close, md.high), md.low), 16))),
        sub(1.0, ts_rank(md.returns, 32)))


def alpha_036(md: MarketData) -> Series:
    # ((((2.21 * rank(correlation((close - open), delay(volume, 1), 15)))
    #  + (0.7 * rank((open - close)))) + (0.73 * rank(Ts_Rank(delay((-1 * returns), 6), 5))))
    #  + rank(abs(correlation(vwap, adv20, 6))))
    #  + (0.6 * rank((((sum(close, 200) / 200) - open) * (close - open)))))
    co = sub(md.close, md.open)
    return add(
        add(
            add(
                add(mul(2.21, rank(correlation(co, delay(md.volume, 1), 15))),
                    mul(0.7, rank(co))),
                mul(0.73, rank(ts_rank(delay(mul(-1, md.returns), 6), 5)))),
            rank(abs_(correlation(md.vwap, md.adv(20), 6)))),
        mul(0.6, rank(mul(
            sub(div(ts_sum(md.close, 200), 200), md.open), co))))


def alpha_037(md: MarketData) -> Series:
    # (rank(correlation(delay((open - close), 1), close, 200)) + rank((open - close)))
    return add(
        rank(correlation(delay(sub(md.open, md.close), 1), md.close, 200)),
        rank(sub(md.open, md.close)))


def alpha_038(md: MarketData) -> Series:
    # ((-1 * rank(Ts_Rank(close, 10))) * rank((close / open)))
    return mul(mul(-1, rank(ts_rank(md.close, 10))),
               rank(div(md.close, md.open)))


def alpha_039(md: MarketData) -> Series:
    # ((-1 * rank((delta(close, 7) * (1 - rank(decay_linear((volume / adv20), 9))))))
    #  * (1 + rank(sum(returns, 250))))
    return mul(
        mul(-1, rank(mul(
            delta(md.close, 7),
            sub(1.0, rank(decay_linear(div(md.volume, md.adv(20)), 9)))))),
        add(1.0, rank(ts_sum(md.returns, 250))))


def alpha_040(md: MarketData) -> Series:
    # ((-1 * rank(stddev(high, 10))) * correlation(high, volume, 10))
    return mul(mul(-1, rank(stddev(md.high, 10))),
               correlation(md.high, md.volume, 10))


def alpha_041(md: MarketData) -> Series:
    # (((high * low)^0.5) - vwap)
    return sub(power(mul(md.high, md.low), 0.5), md.vwap)


def alpha_042(md: MarketData) -> Series:
    # (rank((vwap - close)) / rank((vwap + close)))
    return div(rank(sub(md.vwap, md.close)),
               rank(add(md.vwap, md.close)))


def alpha_043(md: MarketData) -> Series:
    # (ts_rank((volume / adv20), 20) * ts_rank((-1 * delta(close, 7)), 8))
    return mul(ts_rank(div(md.volume, md.adv(20)), 20),
               ts_rank(mul(-1, delta(md.close, 7)), 8))


def alpha_044(md: MarketData) -> Series:
    # (-1 * correlation(high, rank(volume), 5))
    return mul(-1, correlation(md.high, rank(md.volume), 5))


def alpha_045(md: MarketData) -> Series:
    # (-1 * ((rank((sum(delay(close, 5), 20) / 20)) * correlation(close, volume, 2))
    #  * rank(correlation(sum(close, 5), sum(close, 20), 2))))
    return mul(-1, mul(
        mul(rank(div(ts_sum(delay(md.close, 5), 20), 20)),
            correlation(md.close, md.volume, 2)),
        rank(correlation(ts_sum(md.close, 5), ts_sum(md.close, 20), 2))))


def _alpha_46_49_51_expr(md: MarketData) -> Series:
    # (((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10))
    return sub(div(sub(delay(md.close, 20), delay(md.close, 10)), 10.0),
               div(sub(delay(md.close, 10), md.close), 10.0))


def alpha_046(md: MarketData) -> Series:
    # ((0.25 < expr) ? (-1 * 1) : ((expr < 0) ? 1 : ((-1 * 1) * (close - delay(close, 1)))))
    e = _alpha_46_49_51_expr(md)
    return where(gt(e, 0.25), -1.0,
                 where(lt(e, 0.0), 1.0,
                       mul(-1.0, sub(md.close, delay(md.close, 1)))))


def alpha_047(md: MarketData) -> Series:
    # ((((rank((1 / close)) * volume) / adv20) * ((high * rank((high - close))) / (sum(high, 5) / 5)))
    #  - rank((vwap - delay(vwap, 5))))
    first = div(mul(rank(div(1.0, md.close)), md.volume), md.adv(20))
    second = div(mul(md.high, rank(sub(md.high, md.close))),
                 div(ts_sum(md.high, 5), 5))
    return sub(mul(first, second),
               rank(sub(md.vwap, delay(md.vwap, 5))))


def alpha_048(md: MarketData) -> Series:
    # (indneutralize(((correlation(delta(close, 1), delta(delay(close, 1), 1), 250) * delta(close, 1)) / close), IndClass.subindustry)
    #  / sum(((delta(close, 1) / delay(close, 1))^2), 250))
    dc = delta(md.close, 1)
    return div(
        div(mul(correlation(dc, delta(delay(md.close, 1), 1), 250), dc),
            md.close),
        ts_sum(power(div(dc, delay(md.close, 1)), 2), 250))


def alpha_049(md: MarketData) -> Series:
    # ((expr < (-1 * 0.1)) ? 1 : ((-1 * 1) * (close - delay(close, 1))))
    e = _alpha_46_49_51_expr(md)
    return where(lt(e, -0.1), 1.0,
                 mul(-1.0, sub(md.close, delay(md.close, 1))))


def alpha_050(md: MarketData) -> Series:
    # (-1 * ts_max(rank(correlation(rank(volume), rank(vwap), 5)), 5))
    return mul(-1, ts_max(
        rank(correlation(rank(md.volume), rank(md.vwap), 5)), 5))


def alpha_051(md: MarketData) -> Series:
    # ((expr < (-1 * 0.05)) ? 1 : ((-1 * 1) * (close - delay(close, 1))))
    e = _alpha_46_49_51_expr(md)
    return where(lt(e, -0.05), 1.0,
                 mul(-1.0, sub(md.close, delay(md.close, 1))))


def alpha_052(md: MarketData) -> Series:
    # ((((-1 * ts_min(low, 5)) + delay(ts_min(low, 5), 5))
    #  * rank(((sum(returns, 240) - sum(returns, 20)) / 220))) * ts_rank(volume, 5))
    return mul(
        mul(add(mul(-1, ts_min(md.low, 5)), delay(ts_min(md.low, 5), 5)),
            rank(div(sub(ts_sum(md.returns, 240), ts_sum(md.returns, 20)),
                     220.0))),
        ts_rank(md.volume, 5))


def alpha_053(md: MarketData) -> Series:
    # (-1 * delta((((close - low) - (high - close)) / (close - low)), 9))
    q = div(sub(sub(md.close, md.low), sub(md.high, md.close)),
            sub(md.close, md.low))
    return mul(-1, delta(q, 9))


def alpha_054(md: MarketData) -> Series:
    # ((-1 * ((low - close) * (open^5))) / ((low - high) * (close^5)))
    return div(
        mul(-1, mul(sub(md.low, md.close), power(md.open, 5))),
        mul(sub(md.low, md.high), power(md.close, 5)))


def alpha_055(md: MarketData) -> Series:
    # (-1 * correlation(rank(((close - ts_min(low, 12)) / (ts_max(high, 12) - ts_min(low, 12)))), rank(volume), 6))
    rng = sub(ts_max(md.high, 12), ts_min(md.low, 12))
    return mul(-1, correlation(
        rank(div(sub(md.close, ts_min(md.low, 12)), rng)),
        rank(md.volume), 6))


def alpha_056(md: MarketData) -> Series:
    # (0 - (1 * (rank((sum(returns, 10) / sum(sum(returns, 2), 3))) * rank((returns * cap)))))
    return mul(-1, mul(
        rank(div(ts_sum(md.returns, 10),
                 ts_sum(ts_sum(md.returns, 2), 3))),
        rank(mul(md.returns, md.cap))))


def alpha_057(md: MarketData) -> Series:
    # (0 - (1 * ((close - vwap) / decay_linear(rank(ts_argmax(close, 30)), 2))))
    return mul(-1, div(
        sub(md.close, md.vwap),
        decay_linear(rank(ts_argmax(md.close, 30)), 2)))


def alpha_058(md: MarketData) -> Series:
    # (-1 * Ts_Rank(decay_linear(correlation(IndNeutralize(vwap, IndClass.sector), volume, 3.92795), 7.89291), 5.50322))
    return mul(-1, ts_rank(
        decay_linear(correlation(md.vwap, md.volume, W(3.92795)),
                     W(7.89291)),
        W(5.50322)))


def alpha_059(md: MarketData) -> Series:
    # (-1 * Ts_Rank(decay_linear(correlation(IndNeutralize(((vwap * 0.728317) + (vwap * (1 - 0.728317))), IndClass.industry), volume, 4.25197), 16.2289), 8.19648))
    return mul(-1, ts_rank(
        decay_linear(correlation(md.vwap, md.volume, W(4.25197)),
                     W(16.2289)),
        W(8.19648)))


def alpha_060(md: MarketData) -> Series:
    # (0 - (1 * ((2 * scale(rank(((((close - low) - (high - close)) / (high - low)) * volume))))
    #  - scale(rank(ts_argmax(close, 10))))))
    q = mul(div(sub(sub(md.close, md.low), sub(md.high, md.close)),
                sub(md.high, md.low)), md.volume)
    return mul(-1, sub(mul(2.0, scale(rank(q))),
                       scale(rank(ts_argmax(md.close, 10)))))


def alpha_061(md: MarketData) -> Series:
    # (rank((vwap - ts_min(vwap, 16.1219))) < rank(correlation(vwap, adv180, 17.9282)))  -> boolean 0/1
    c = lt(rank(sub(md.vwap, ts_min(md.vwap, W(16.1219)))),
           rank(correlation(md.vwap, md.adv(180), W(17.9282))))
    return [None if v is None else (1.0 if v else 0.0) for v in c]


def alpha_062(md: MarketData) -> Series:
    # ((rank(correlation(vwap, sum(adv20, 22.4101), 9.91009))
    #  < rank(((rank(open) + rank(open)) < (rank(((high + low) / 2)) + rank(high))))) * -1)
    inner = lt(add(rank(md.open), rank(md.open)),
               add(rank(div(add(md.high, md.low), 2.0)), rank(md.high)))
    inner_num = [None if v is None else (1.0 if v else 0.0) for v in inner]
    c = lt(rank(correlation(md.vwap, ts_sum(md.adv(20), W(22.4101)),
                            W(9.91009))),
           rank(inner_num))
    return [None if v is None else (-1.0 if v else 0.0) for v in c]


def alpha_063(md: MarketData) -> Series:
    # ((rank(decay_linear(delta(IndNeutralize(close, IndClass.industry), 2.25164), 8.22237))
    #  - rank(decay_linear(correlation(((vwap * 0.318108) + (open * (1 - 0.318108))), sum(adv180, 37.2467), 13.557), 12.2883))) * -1)
    mixed = add(mul(md.vwap, 0.318108), mul(md.open, 0.681892))
    return mul(-1, sub(
        rank(decay_linear(delta(md.close, W(2.25164)), W(8.22237))),
        rank(decay_linear(
            correlation(mixed, ts_sum(md.adv(180), W(37.2467)), W(13.557)),
            W(12.2883)))))


def alpha_064(md: MarketData) -> Series:
    # ((rank(correlation(sum(((open * 0.178404) + (low * (1 - 0.178404))), 12.7054), sum(adv120, 12.7054), 16.6208))
    #  < rank(delta((((high + low) / 2) * 0.178404) + (vwap * (1 - 0.178404))), 3.69741))) * -1)
    mixed1 = add(mul(md.open, 0.178404), mul(md.low, 0.821596))
    mixed2 = add(mul(div(add(md.high, md.low), 2.0), 0.178404),
                 mul(md.vwap, 0.821596))
    c = lt(
        rank(correlation(ts_sum(mixed1, W(12.7054)),
                         ts_sum(md.adv(120), W(12.7054)), W(16.6208))),
        rank(delta(mixed2, W(3.69741))))
    return [None if v is None else (-1.0 if v else 0.0) for v in c]


def alpha_065(md: MarketData) -> Series:
    # ((rank(correlation(((open * 0.00817205) + (vwap * (1 - 0.00817205))), sum(adv60, 8.6911), 6.40374))
    #  < rank((open - ts_min(open, 13.635)))) * -1)
    mixed = add(mul(md.open, 0.00817205), mul(md.vwap, 0.99182795))
    c = lt(
        rank(correlation(mixed, ts_sum(md.adv(60), W(8.6911)), W(6.40374))),
        rank(sub(md.open, ts_min(md.open, W(13.635)))))
    return [None if v is None else (-1.0 if v else 0.0) for v in c]


def alpha_066(md: MarketData) -> Series:
    # ((rank(decay_linear(delta(vwap, 3.51013), 7.23052))
    #  + Ts_Rank(decay_linear(((((low * 0.96633) + (low * (1 - 0.96633))) - vwap) / (open - ((high + low) / 2))), 11.4157), 6.72611)) * -1)
    q = div(sub(md.low, md.vwap),
            sub(md.open, div(add(md.high, md.low), 2.0)))
    return mul(-1, add(
        rank(decay_linear(delta(md.vwap, W(3.51013)), W(7.23052))),
        ts_rank(decay_linear(q, W(11.4157)), W(6.72611))))


def alpha_067(md: MarketData) -> Series:
    # ((rank((high - ts_min(high, 2.14593)))^rank(correlation(IndNeutralize(vwap, IndClass.sector), IndNeutralize(adv20, IndClass.subindustry), 6.02936))) * -1)
    return mul(-1, signed_power(
        rank(sub(md.high, ts_min(md.high, W(2.14593)))),
        rank(correlation(md.vwap, md.adv(20), W(6.02936)))))


def alpha_068(md: MarketData) -> Series:
    # ((Ts_Rank(correlation(rank(high), rank(adv15), 8.91644), 13.9333)
    #  < rank(delta(((close * 0.518371) + (low * (1 - 0.518371))), 1.06157))) * -1)
    mixed = add(mul(md.close, 0.518371), mul(md.low, 0.481629))
    c = lt(
        ts_rank(correlation(rank(md.high), rank(md.adv(15)), W(8.91644)),
                W(13.9333)),
        rank(delta(mixed, W(1.06157))))
    return [None if v is None else (-1.0 if v else 0.0) for v in c]


def alpha_069(md: MarketData) -> Series:
    # ((rank(ts_max(delta(IndNeutralize(vwap, IndClass.industry), 2.72412), 4.79344))
    #  ^Ts_Rank(correlation(((close * 0.490655) + (vwap * (1 - 0.490655))), adv20, 4.92416), 9.0615)) * -1)
    mixed = add(mul(md.close, 0.490655), mul(md.vwap, 0.509345))
    return mul(-1, signed_power(
        rank(ts_max(delta(md.vwap, W(2.72412)), W(4.79344))),
        ts_rank(correlation(mixed, md.adv(20), W(4.92416)), W(9.0615))))


def alpha_070(md: MarketData) -> Series:
    # ((rank(delta(vwap, 1.29456))^Ts_Rank(correlation(IndNeutralize(close, IndClass.industry), adv50, 17.8256), 17.9171)) * -1)
    return mul(-1, signed_power(
        rank(delta(md.vwap, W(1.29456))),
        ts_rank(correlation(md.close, md.adv(50), W(17.8256)), W(17.9171))))


def alpha_071(md: MarketData) -> Series:
    # max(Ts_Rank(decay_linear(correlation(Ts_Rank(close, 3.43976), Ts_Rank(adv180, 12.0647), 18.0175), 4.20501), 15.6948),
    #  Ts_Rank(decay_linear((rank(((low + open) - (vwap + vwap)))^2), 16.4662), 4.4388))
    return max_(
        ts_rank(decay_linear(
            correlation(ts_rank(md.close, W(3.43976)),
                        ts_rank(md.adv(180), W(12.0647)), W(18.0175)),
            W(4.20501)), W(15.6948)),
        ts_rank(decay_linear(
            power(rank(sub(add(md.low, md.open), add(md.vwap, md.vwap))), 2),
            W(16.4662)), W(4.4388)))


def alpha_072(md: MarketData) -> Series:
    # (rank(decay_linear(correlation(((high + low) / 2), adv40, 8.93345), 10.1519))
    #  / rank(decay_linear(correlation(Ts_Rank(vwap, 3.72469), Ts_Rank(volume, 18.5188), 6.86671), 2.95011)))
    return div(
        rank(decay_linear(correlation(div(add(md.high, md.low), 2.0),
                                      md.adv(40), W(8.93345)), W(10.1519))),
        rank(decay_linear(
            correlation(ts_rank(md.vwap, W(3.72469)),
                        ts_rank(md.volume, W(18.5188)), W(6.86671)),
            W(2.95011))))


def alpha_073(md: MarketData) -> Series:
    # (max(rank(decay_linear(delta(vwap, 4.72775), 2.91864)),
    #  Ts_Rank(decay_linear(((delta(((open * 0.147155) + (low * (1 - 0.147155))), 2.03608) / ((open * 0.147155) + (low * (1 - 0.147155)))) * -1), 3.33829), 16.7411)) * -1)
    mixed = add(mul(md.open, 0.147155), mul(md.low, 0.852845))
    return mul(-1, max_(
        rank(decay_linear(delta(md.vwap, W(4.72775)), W(2.91864))),
        ts_rank(decay_linear(mul(-1, div(delta(mixed, W(2.03608)), mixed)),
                            W(3.33829)), W(16.7411))))


def alpha_074(md: MarketData) -> Series:
    # ((rank(correlation(close, sum(adv30, 37.4843), 15.1365))
    #  < rank(correlation(rank(((high * 0.0261661) + (vwap * (1 - 0.0261661)))), rank(volume), 11.4791))) * -1)
    mixed = add(mul(md.high, 0.0261661), mul(md.vwap, 0.9738339))
    c = lt(
        rank(correlation(md.close, ts_sum(md.adv(30), W(37.4843)),
                         W(15.1365))),
        rank(correlation(rank(mixed), rank(md.volume), W(11.4791))))
    return [None if v is None else (-1.0 if v else 0.0) for v in c]


def alpha_075(md: MarketData) -> Series:
    # (rank(correlation(vwap, volume, 4.24304)) < rank(correlation(rank(low), rank(adv50), 12.4413)))  -> boolean 0/1
    c = lt(
        rank(correlation(md.vwap, md.volume, W(4.24304))),
        rank(correlation(rank(md.low), rank(md.adv(50)), W(12.4413))))
    return [None if v is None else (1.0 if v else 0.0) for v in c]


def alpha_076(md: MarketData) -> Series:
    # (max(rank(decay_linear(delta(vwap, 1.24383), 11.8259)),
    #  Ts_Rank(decay_linear(Ts_Rank(correlation(IndNeutralize(low, IndClass.sector), adv81, 8.14941), 19.569), 17.1543), 19.383)) * -1)
    return mul(-1, max_(
        rank(decay_linear(delta(md.vwap, W(1.24383)), W(11.8259))),
        ts_rank(decay_linear(
            ts_rank(correlation(md.low, md.adv(81), W(8.14941)), W(19.569)),
            W(17.1543)), W(19.383))))


def alpha_077(md: MarketData) -> Series:
    # min(rank(decay_linear(((((high + low) / 2) + high) - (vwap + high)), 20.0451)),
    #  rank(decay_linear(correlation(((high + low) / 2), adv40, 3.1614), 5.64125)))
    hl = div(add(md.high, md.low), 2.0)
    return min_(
        rank(decay_linear(sub(add(hl, md.high), add(md.vwap, md.high)),
                          W(20.0451))),
        rank(decay_linear(correlation(hl, md.adv(40), W(3.1614)), W(5.64125))))


def alpha_078(md: MarketData) -> Series:
    # (rank(correlation(sum(((low * 0.352233) + (vwap * (1 - 0.352233))), 19.7428), sum(adv40, 19.7428), 6.83313))
    #  ^rank(correlation(rank(vwap), rank(volume), 5.77492)))
    mixed = add(mul(md.low, 0.352233), mul(md.vwap, 0.647767))
    return signed_power(
        rank(correlation(ts_sum(mixed, W(19.7428)),
                         ts_sum(md.adv(40), W(19.7428)), W(6.83313))),
        rank(correlation(rank(md.vwap), rank(md.volume), W(5.77492))))


def alpha_079(md: MarketData) -> Series:
    # (rank(delta(IndNeutralize(((close * 0.60733) + (open * (1 - 0.60733))), IndClass.sector), 1.23438))
    #  < rank(correlation(Ts_Rank(vwap, 3.60973), Ts_Rank(adv150, 9.18637), 14.6644)))  -> boolean 0/1
    mixed = add(mul(md.close, 0.60733), mul(md.open, 0.39267))
    c = lt(
        rank(delta(mixed, W(1.23438))),
        rank(correlation(ts_rank(md.vwap, W(3.60973)),
                         ts_rank(md.adv(150), W(9.18637)), W(14.6644))))
    return [None if v is None else (1.0 if v else 0.0) for v in c]


def alpha_080(md: MarketData) -> Series:
    # ((rank(Sign(delta(IndNeutralize(((open * 0.868128) + (high * (1 - 0.868128))), IndClass.industry), 4.04545)))
    #  ^Ts_Rank(correlation(high, adv10, 5.11456), 5.53756)) * -1)
    mixed = add(mul(md.open, 0.868128), mul(md.high, 0.131872))
    return mul(-1, signed_power(
        rank(sign(delta(mixed, W(4.04545)))),
        ts_rank(correlation(md.high, md.adv(10), W(5.11456)), W(5.53756))))


def alpha_081(md: MarketData) -> Series:
    # ((rank(Log(product(rank((rank(correlation(vwap, sum(adv10, 49.6054), 8.47743))^4)), 14.9655)))
    #  < rank(correlation(rank(vwap), rank(volume), 5.07914))) * -1)
    c = lt(
        rank(log_(product(
            rank(power(rank(correlation(
                md.vwap, ts_sum(md.adv(10), W(49.6054)), W(8.47743))), 4)),
            W(14.9655)))),
        rank(correlation(rank(md.vwap), rank(md.volume), W(5.07914))))
    return [None if v is None else (-1.0 if v else 0.0) for v in c]


def alpha_082(md: MarketData) -> Series:
    # (min(rank(decay_linear(delta(open, 1.46063), 14.8717)),
    #  Ts_Rank(decay_linear(correlation(IndNeutralize(volume, IndClass.sector), ((open * 0.634196) + (open * (1 - 0.634196))), 17.4842), 6.92131), 13.4283)) * -1)
    return mul(-1, min_(
        rank(decay_linear(delta(md.open, W(1.46063)), W(14.8717))),
        ts_rank(decay_linear(
            correlation(md.volume, md.open, W(17.4842)), W(6.92131)),
            W(13.4283))))


def alpha_083(md: MarketData) -> Series:
    # ((rank(delay(((high - low) / (sum(close, 5) / 5)), 2)) * rank(rank(volume)))
    #  / (((high - low) / (sum(close, 5) / 5)) / (vwap - close)))
    q = div(sub(md.high, md.low), div(ts_sum(md.close, 5), 5))
    return div(mul(rank(delay(q, 2)), rank(rank(md.volume))),
               div(q, sub(md.vwap, md.close)))


def alpha_084(md: MarketData) -> Series:
    # SignedPower(Ts_Rank((vwap - ts_max(vwap, 15.3217)), 20.7127), delta(close, 4.96796))
    return signed_power(
        ts_rank(sub(md.vwap, ts_max(md.vwap, W(15.3217))), W(20.7127)),
        delta(md.close, W(4.96796)))


def alpha_085(md: MarketData) -> Series:
    # (rank(correlation(((high * 0.876703) + (close * (1 - 0.876703))), adv30, 9.61331))
    #  ^rank(correlation(Ts_Rank(((high + low) / 2), 3.70596), Ts_Rank(volume, 10.1595), 7.11408)))
    mixed = add(mul(md.high, 0.876703), mul(md.close, 0.123297))
    return signed_power(
        rank(correlation(mixed, md.adv(30), W(9.61331))),
        rank(correlation(ts_rank(div(add(md.high, md.low), 2.0), W(3.70596)),
                         ts_rank(md.volume, W(10.1595)), W(7.11408))))


def alpha_086(md: MarketData) -> Series:
    # ((Ts_Rank(correlation(close, sum(adv20, 14.7444), 6.00049), 20.4195)
    #  < rank(((open + close) - (vwap + open)))) * -1)
    c = lt(
        ts_rank(correlation(md.close, ts_sum(md.adv(20), W(14.7444)),
                            W(6.00049)), W(20.4195)),
        rank(sub(add(md.open, md.close), add(md.vwap, md.open))))
    return [None if v is None else (-1.0 if v else 0.0) for v in c]


def alpha_087(md: MarketData) -> Series:
    # (max(rank(decay_linear(delta(((close * 0.369701) + (vwap * (1 - 0.369701))), 1.91233), 2.65461)),
    #  Ts_Rank(decay_linear(abs(correlation(IndNeutralize(adv81, IndClass.industry), close, 13.4132)), 4.89768), 14.4535)) * -1)
    mixed = add(mul(md.close, 0.369701), mul(md.vwap, 0.630299))
    return mul(-1, max_(
        rank(decay_linear(delta(mixed, W(1.91233)), W(2.65461))),
        ts_rank(decay_linear(
            abs_(correlation(md.adv(81), md.close, W(13.4132))),
            W(4.89768)), W(14.4535))))


def alpha_088(md: MarketData) -> Series:
    # min(rank(decay_linear(((rank(open) + rank(low)) - (rank(high) + rank(close))), 8.06882)),
    #  Ts_Rank(decay_linear(correlation(Ts_Rank(close, 8.44728), Ts_Rank(adv60, 20.6966), 8.01266), 6.65053), 2.61957))
    return min_(
        rank(decay_linear(
            sub(add(rank(md.open), rank(md.low)),
                add(rank(md.high), rank(md.close))), W(8.06882))),
        ts_rank(decay_linear(
            correlation(ts_rank(md.close, W(8.44728)),
                        ts_rank(md.adv(60), W(20.6966)), W(8.01266)),
            W(6.65053)), W(2.61957)))


def alpha_089(md: MarketData) -> Series:
    # (Ts_Rank(decay_linear(correlation(((low * 0.967285) + (low * (1 - 0.967285))), adv10, 6.94279), 5.51607), 3.79744)
    #  - Ts_Rank(decay_linear(delta(IndNeutralize(vwap, IndClass.industry), 3.48158), 10.1466), 15.3012))
    return sub(
        ts_rank(decay_linear(correlation(md.low, md.adv(10), W(6.94279)),
                             W(5.51607)), W(3.79744)),
        ts_rank(decay_linear(delta(md.vwap, W(3.48158)), W(10.1466)),
                W(15.3012)))


def alpha_090(md: MarketData) -> Series:
    # ((rank((close - ts_max(close, 4.66719)))^Ts_Rank(correlation(IndNeutralize(adv40, IndClass.subindustry), low, 5.38375), 3.21856)) * -1)
    return mul(-1, signed_power(
        rank(sub(md.close, ts_max(md.close, W(4.66719)))),
        ts_rank(correlation(md.adv(40), md.low, W(5.38375)), W(3.21856))))


def alpha_091(md: MarketData) -> Series:
    # ((Ts_Rank(decay_linear(decay_linear(correlation(IndNeutralize(close, IndClass.industry), volume, 9.74928), 16.398), 3.83219), 4.8667)
    #  - rank(decay_linear(correlation(vwap, adv30, 4.01303), 2.6809))) * -1)
    return mul(-1, sub(
        ts_rank(decay_linear(
            decay_linear(correlation(md.close, md.volume, W(9.74928)),
                         W(16.398)), W(3.83219)), W(4.8667)),
        rank(decay_linear(correlation(md.vwap, md.adv(30), W(4.01303)),
                          W(2.6809)))))


def alpha_092(md: MarketData) -> Series:
    # min(Ts_Rank(decay_linear(((((high + low) / 2) + close) < (low + open)), 14.7221), 18.8683),
    #  Ts_Rank(decay_linear(correlation(rank(low), rank(adv30), 7.58555), 6.94024), 6.80584))
    c = lt(add(div(add(md.high, md.low), 2.0), md.close),
           add(md.low, md.open))
    c_num = [None if v is None else (1.0 if v else 0.0) for v in c]
    return min_(
        ts_rank(decay_linear(c_num, W(14.7221)), W(18.8683)),
        ts_rank(decay_linear(
            correlation(rank(md.low), rank(md.adv(30)), W(7.58555)),
            W(6.94024)), W(6.80584)))


def alpha_093(md: MarketData) -> Series:
    # (Ts_Rank(decay_linear(correlation(IndNeutralize(vwap, IndClass.industry), adv81, 17.4193), 19.848), 7.54455)
    #  / rank(decay_linear(delta(((close * 0.524434) + (vwap * (1 - 0.524434))), 2.77377), 16.2664)))
    mixed = add(mul(md.close, 0.524434), mul(md.vwap, 0.475566))
    return div(
        ts_rank(decay_linear(correlation(md.vwap, md.adv(81), W(17.4193)),
                             W(19.848)), W(7.54455)),
        rank(decay_linear(delta(mixed, W(2.77377)), W(16.2664))))


def alpha_094(md: MarketData) -> Series:
    # ((rank((vwap - ts_min(vwap, 11.5783)))^Ts_Rank(correlation(Ts_Rank(vwap, 19.6462), Ts_Rank(adv60, 4.02992), 18.0926), 2.70756)) * -1)
    return mul(-1, signed_power(
        rank(sub(md.vwap, ts_min(md.vwap, W(11.5783)))),
        ts_rank(correlation(ts_rank(md.vwap, W(19.6462)),
                            ts_rank(md.adv(60), W(4.02992)), W(18.0926)),
                W(2.70756))))


def alpha_095(md: MarketData) -> Series:
    # (rank((open - ts_min(open, 12.4105))) < Ts_Rank((rank(correlation(sum(((high + low) / 2), 19.1351), sum(adv40, 19.1351), 12.8742))^5), 11.7584))
    hl = div(add(md.high, md.low), 2.0)
    c = lt(
        rank(sub(md.open, ts_min(md.open, W(12.4105)))),
        ts_rank(power(rank(correlation(
            ts_sum(hl, W(19.1351)), ts_sum(md.adv(40), W(19.1351)),
            W(12.8742))), 5), W(11.7584)))
    return [None if v is None else (1.0 if v else 0.0) for v in c]


def alpha_096(md: MarketData) -> Series:
    # (max(Ts_Rank(decay_linear(correlation(rank(vwap), rank(volume), 3.83878), 4.16783), 8.38151),
    #  Ts_Rank(decay_linear(Ts_ArgMax(correlation(Ts_Rank(close, 7.45404), Ts_Rank(adv60, 4.13242), 3.65459), 12.6556), 14.0365), 13.4143)) * -1)
    return mul(-1, max_(
        ts_rank(decay_linear(
            correlation(rank(md.vwap), rank(md.volume), W(3.83878)),
            W(4.16783)), W(8.38151)),
        ts_rank(decay_linear(
            ts_argmax(correlation(ts_rank(md.close, W(7.45404)),
                                  ts_rank(md.adv(60), W(4.13242)),
                                  W(3.65459)), W(12.6556)),
            W(14.0365)), W(13.4143))))


def alpha_097(md: MarketData) -> Series:
    # ((rank(decay_linear(delta(IndNeutralize(((low * 0.721001) + (vwap * (1 - 0.721001))), IndClass.industry), 3.3705), 20.4523))
    #  - Ts_Rank(decay_linear(Ts_Rank(correlation(Ts_Rank(low, 7.87871), Ts_Rank(adv60, 17.255), 4.97547), 18.5925), 15.7152), 6.71659)) * -1)
    mixed = add(mul(md.low, 0.721001), mul(md.vwap, 0.278999))
    return mul(-1, sub(
        rank(decay_linear(delta(mixed, W(3.3705)), W(20.4523))),
        ts_rank(decay_linear(
            ts_rank(correlation(ts_rank(md.low, W(7.87871)),
                                ts_rank(md.adv(60), W(17.255)), W(4.97547)),
                    W(18.5925)), W(15.7152)), W(6.71659))))


def alpha_098(md: MarketData) -> Series:
    # (rank(decay_linear(correlation(vwap, sum(adv5, 26.4719), 4.58418), 7.18088))
    #  - rank(decay_linear(Ts_Rank(Ts_ArgMin(correlation(rank(open), rank(adv15), 20.8187), 8.62571), 6.95668), 8.07206)))
    return sub(
        rank(decay_linear(
            correlation(md.vwap, ts_sum(md.adv(5), W(26.4719)), W(4.58418)),
            W(7.18088))),
        rank(decay_linear(
            ts_rank(ts_argmin(correlation(rank(md.open), rank(md.adv(15)),
                                          W(20.8187)), W(8.62571)),
                   W(6.95668)), W(8.07206))))


def alpha_099(md: MarketData) -> Series:
    # ((rank(correlation(sum(((high + low) / 2), 19.8975), sum(adv60, 19.8975), 8.8136))
    #  < rank(correlation(low, volume, 6.28259))) * -1)
    hl = div(add(md.high, md.low), 2.0)
    c = lt(
        rank(correlation(ts_sum(hl, W(19.8975)), ts_sum(md.adv(60), W(19.8975)),
                         W(8.8136))),
        rank(correlation(md.low, md.volume, W(6.28259))))
    return [None if v is None else (-1.0 if v else 0.0) for v in c]


def alpha_100(md: MarketData) -> Series:
    # (0 - (1 * (((1.5 * scale(indneutralize(indneutralize(rank(((((close - low) - (high - close)) / (high - low)) * volume)), IndClass.subindustry), IndClass.subindustry)))
    #  - scale(indneutralize((correlation(close, rank(adv20), 5) - rank(ts_argmin(close, 30))), IndClass.subindustry))) * (volume / adv20))))
    q = mul(div(sub(sub(md.close, md.low), sub(md.high, md.close)),
                sub(md.high, md.low)), md.volume)
    return mul(-1, mul(
        sub(mul(1.5, scale(rank(q))),
            scale(sub(correlation(md.close, rank(md.adv(20)), 5),
                      rank(ts_argmin(md.close, 30))))),
        div(md.volume, md.adv(20))))


def alpha_101(md: MarketData) -> Series:
    # ((close - open) / ((high - low) + .001))
    return div(sub(md.close, md.open),
               add(sub(md.high, md.low), 0.001))


# --------------------------------------------------------------------------- #
# Registry                                                                     #
# --------------------------------------------------------------------------- #
ALPHA_FUNCS: dict[str, AlphaFn] = {
    f"Alpha{i:03d}": globals()[f"alpha_{i:03d}"] for i in range(1, 102)
}
ALPHA_IDS: list[str] = list(ALPHA_FUNCS.keys())


def compute_alpha(alpha_id: str, md: MarketData) -> Series:
    """Compute one alpha over the full MarketData history."""
    return ALPHA_FUNCS[alpha_id](md)
