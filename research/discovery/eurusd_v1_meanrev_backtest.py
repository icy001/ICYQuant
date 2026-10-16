#!/usr/bin/env python3
"""EURUSD mean reversion ("high-sell / low-buy") -- V1 baseline and V2 trend gate.

Purpose
-------
A honest read on whether "sell strength at range highs, buy weakness at range
lows with a reversal-confirmation candle" makes money on YOUR real EURUSD
history. Parameters are stated up front, never fitted silently.

V1 verdict -- measured with this file, kept as the record
---------------------------------------------------------
window=20, stop=2.0 ATR -> 540 trades, win 53.3%, payoff 0.85, PF 0.995,
NET -977.5 pips (-$9,775 on 1 lot), max DD -$27,546, Sharpe -0.048.

The decisive number was GROSS -167.5 pips: even at ZERO cost it loses, so the
entry rule itself carries no edge and transaction cost only amplified it. The
best-looking variant (window=30 / stop=3.0, net +1,556 pips) was unpacked and
rejected rather than adopted: its max drawdown (-3,237 pips) is 2.1x its net
gain, Sharpe 0.078 is indistinguishable from random, and its 5-year segments
alternate sign (-437, +1,835, -1,882, +200, +2,210, -370) -- regime luck, not a
parameter plateau.

V2 change -- trade it only when the market is NOT trending
----------------------------------------------------------
V1's losses cluster in trending stretches: 2010-2014 lost 1,882 pips while
EURUSD slid 1.45 -> 1.20 and "buy the dip" kept catching a falling knife. So V2
keeps the IDENTICAL entry and exit and merely gates it on ADX -- take the signal
only when ADX < --adx-max, stay flat otherwise. Nothing else moves. That makes
the comparison interpretable: any difference is the regime filter and nothing
else. The baseline (no gate) is always run and printed side by side on the same
bars, so the two never differ by data window.

A regime filter is CHOSEN, not derived, so the ADX threshold is swept and every
time segment is reported. A result that survives only at one magic threshold is
fitting, not an edge.

Data (real, already built from your raw files)
----------------------------------------------
artifacts/histdata_v9/derived/eurusd_2000-2026_d1.parquet
    <- artifacts/histdata_v9/parsed/eurusd_2000-2026_bars.parquet
    <- data/real/histdata/HISTDATA_COM_ASCII_EURUSD_M1<year>/DAT_ASCII_EURUSD_M1_<year>.csv
    8126 daily bars, 2000-05-30 .. 2026-10-02, from 8,999,733 M1 rows.

Honesty rules baked in
----------------------
1. NO LOOK-AHEAD. The range that triggers bar i comes from bars [i-N .. i-1];
   bar i never takes part in the level that triggers it, so the trigger cannot be
   circular. A signal completing at bar i's close FILLS AT BAR i+1's OPEN.
2. CONSERVATIVE STOP/TARGET ORDERING. If one bar could reach both, it is booked
   as the STOP. Optimistic ordering is the easiest way to fake a good backtest.
3. COSTS ALWAYS CHARGED, and both gross and net are reported side by side.
4. SAME BARS FOR EVERYTHING. Baseline and gated variants drop identical warmup
   bars, so no comparison is won by trading a longer sample.

Known limits of this dataset (reported, never silently ignored)
---------------------------------------------------------------
* `volume` is identically 0 in HistData ASCII -- nothing here uses it.
* One spike bar (2001-06-07, price 1965.0001) was already quarantined upstream.
* Days whose M1 bar count is below --min-bars are dropped: too few ticks to be a
  real trading day.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DEFAULT_DATA = REPO / "artifacts/histdata_v9/derived/eurusd_2000-2026_d1.parquet"
DEFAULT_OUT = REPO / "artifacts/research/eurusd_meanrev"

PIP = 0.0001        # EURUSD: 1 pip of price
LOT = 100_000       # 1 standard lot -> 1 pip == 10 USD on EURUSD
USD_PER_PIP = PIP * LOT   # == 10.0


# --------------------------------------------------------------------------- #
# Features. Every level used at bar i is known no later than bar i's close.
# --------------------------------------------------------------------------- #
def wilder_adx(f: pd.DataFrame, n: int) -> pd.Series:
    """Wilder ADX. Convention here: HIGH adx == trending, LOW adx == choppy.

    Mean reversion lives in chop, so V2 gates entries on adx being LOW.
    Causal: only bars up to and including i are used at bar i.
    """
    up = f["high"].diff()
    dn = -f["low"].diff()
    plus_dm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=f.index)
    minus_dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=f.index)
    prev_close = f["close"].shift(1)
    tr = np.maximum(
        f["high"] - f["low"],
        np.maximum((f["high"] - prev_close).abs(), (f["low"] - prev_close).abs()),
    )
    sm = dict(alpha=1.0 / n, adjust=False, min_periods=n)
    atr = tr.ewm(**sm).mean()
    pdi = 100.0 * plus_dm.ewm(**sm).mean() / atr
    mdi = 100.0 * minus_dm.ewm(**sm).mean() / atr
    dx = 100.0 * (pdi - mdi).abs() / (pdi + mdi).replace(0.0, np.nan)
    return dx.ewm(**sm).mean()


def compute_features(df: pd.DataFrame, window: int,
                     adx_period: int = 14) -> pd.DataFrame:
    f = df.copy()
    prev_close = f["close"].shift(1)
    tr = np.maximum(
        f["high"] - f["low"],
        np.maximum((f["high"] - prev_close).abs(), (f["low"] - prev_close).abs()),
    )
    # Wilder ATR.
    f["atr"] = tr.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    # Range of the PREVIOUS `window` bars. `.rolling().max()` at bar i spans
    # [i-w+1 .. i]; shifting by one makes it [i-w .. i-1], i.e. it excludes the
    # bar being judged. Without the shift the entry trigger is self-fulfilling.
    f["range_high"] = f["high"].rolling(window).max().shift(1)
    f["range_low"] = f["low"].rolling(window).min().shift(1)
    f["range_mid"] = (f["range_high"] + f["range_low"]) / 2.0
    f["adx"] = wilder_adx(f, adx_period)
    return f


# --------------------------------------------------------------------------- #
# Backtest engine
# --------------------------------------------------------------------------- #
def backtest(f: pd.DataFrame, *, window: int, eps: float, stop_atr: float,
             max_hold: int, cost_rt_pips: float,
             take_target: bool = True,
             adx_max: float | None = None) -> tuple[list[dict], np.ndarray]:
    """Returns (trades, equity_in_pips_per_bar).

    `adx_max`: take a signal only while ADX < adx_max. None disables the gate,
    which is exactly the V1 behaviour. Everything else is unchanged between V1
    and V2 so the comparison isolates the regime filter.

    Equity is marked to market each bar: realised P&L plus the open position's
    floating P&L less the half of cost already incurred on entry.
    """
    opens = f["open"].to_numpy(float)
    highs = f["high"].to_numpy(float)
    lows = f["low"].to_numpy(float)
    closes = f["close"].to_numpy(float)
    atr = f["atr"].to_numpy(float)
    rh = f["range_high"].to_numpy(float)
    rl = f["range_low"].to_numpy(float)
    mid = f["range_mid"].to_numpy(float)
    adxv = (f["adx"].to_numpy(float) if "adx" in f.columns
            else np.full(len(f), np.nan))
    dates = pd.to_datetime(f["date"]).to_numpy()
    n = len(f)

    trades: list[dict] = []
    equity = np.zeros(n, dtype=float)
    realised = 0.0
    pos: dict | None = None

    for i in range(n):
        # ---- 1. exits first, evaluated inside the bar ---------------------
        if pos is not None:
            side = pos["side"]
            exit_px = None
            reason = None
            # Conservative ordering: the stop wins ties. See honesty rule 2.
            if side == 1:
                if lows[i] <= pos["stop"]:
                    exit_px, reason = pos["stop"], "stop"
                elif take_target and highs[i] >= pos["target"]:
                    exit_px, reason = pos["target"], "target"
            else:
                if highs[i] >= pos["stop"]:
                    exit_px, reason = pos["stop"], "stop"
                elif take_target and lows[i] <= pos["target"]:
                    exit_px, reason = pos["target"], "target"

            held = i - pos["entry_i"]
            if exit_px is None and held >= max_hold:
                exit_px, reason = closes[i], "time"

            if exit_px is not None:
                gross = side * (exit_px - pos["entry_px"]) / PIP
                net = gross - cost_rt_pips
                realised += net
                trades.append({
                    "signal_date": str(np.datetime_as_string(dates[pos["sig_i"]], unit="D")),
                    "entry_date": str(np.datetime_as_string(dates[pos["entry_i"]], unit="D")),
                    "exit_date": str(np.datetime_as_string(dates[i], unit="D")),
                    "side": "long" if side == 1 else "short",
                    "entry_px": round(pos["entry_px"], 5),
                    "exit_px": round(exit_px, 5),
                    "bars_held": int(held),
                    "exit_reason": reason,
                    "adx_at_signal": round(float(adxv[pos["sig_i"]]), 2)
                                    if np.isfinite(adxv[pos["sig_i"]]) else None,
                    "gross_pips": round(gross, 2),
                    "net_pips": round(net, 2),
                    "net_usd_1lot": round(net * USD_PER_PIP, 2),
                })
                pos = None

        # ---- 2. entry signalled at bar i close, filled at bar i+1 open ----
        if pos is None and i + 1 < n and np.isfinite(atr[i]) and np.isfinite(rh[i]):
            # Regime gate (V2): a trending market turns "buy the dip" into
            # catching a falling knife, so trend days are skipped entirely.
            gate_ok = True
            if adx_max is not None:
                gate_ok = bool(np.isfinite(adxv[i]) and adxv[i] < adx_max)
            touched_low = lows[i] <= rl[i] * (1.0 + eps)
            touched_high = highs[i] >= rh[i] * (1.0 - eps)
            bull = touched_low and closes[i] > opens[i]     # hammer at the floor
            bear = touched_high and closes[i] < opens[i]    # shooting star at the ceil
            if gate_ok and (bull or bear):
                side = 1 if bull else -1
                entry_px = float(opens[i + 1])
                a = float(atr[i])
                stop = entry_px - side * stop_atr * a
                pos = {"side": side, "sig_i": i, "entry_i": i + 1,
                       "entry_px": entry_px, "stop": stop,
                       "target": float(mid[i])}

        # ---- 3. mark to market ------------------------------------------
        if pos is None:
            equity[i] = realised
        else:
            floating = pos["side"] * (closes[i] - pos["entry_px"]) / PIP
            equity[i] = realised + floating - cost_rt_pips / 2.0

    return trades, equity


def run_case(raw: pd.DataFrame, *, window: int, eps: float, stop_atr: float,
             max_hold: int, cost_rt_pips: float, take_target: bool,
             adx_max: float | None, adx_period: int):
    """Features -> bars -> trades -> equity, for one parameter set.

    The 'adx' column is always required in the dropna so that the gated and
    ungated runs see byte-identical bars. Without this the comparison could be
    won simply by trading a longer window.
    """
    f = compute_features(raw, window, adx_period)
    f = f.dropna(subset=["atr", "range_high", "range_low", "adx"])
    f = f.reset_index(drop=True)
    trades, equity = backtest(
        f, window=window, eps=eps, stop_atr=stop_atr, max_hold=max_hold,
        cost_rt_pips=cost_rt_pips, take_target=take_target, adx_max=adx_max)
    return f, trades, equity


# --------------------------------------------------------------------------- #
# Metrics. Names follow research/discovery/backtest.py::Metrics so results stay
# comparable with the platform's own reporting.
# --------------------------------------------------------------------------- #
def summarise(trades: list[dict], equity: np.ndarray, *, cost_rt_pips: float,
              label: str) -> dict:
    if not trades:
        return {"label": label, "trade_count": 0}

    net = np.array([t["net_pips"] for t in trades])
    gross = np.array([t["gross_pips"] for t in trades])
    wins, losses = net[net > 0], net[net <= 0]
    gp = gross[gross > 0].sum()
    gl = -gross[gross <= 0].sum()

    peak = np.maximum.accumulate(equity)
    dd = equity - peak
    max_dd = dd.min() if len(dd) else 0.0

    step = np.diff(equity, prepend=equity[0])
    sharpe = 0.0
    if step.std() > 0:
        sharpe = step.mean() / step.std() * np.sqrt(252)

    in_market = sum(max(t["bars_held"], 1) for t in trades)
    return {
        "label": label,
        "trade_count": len(trades),
        "win_rate": round(len(wins) / len(net), 4),
        "avg_win_pips": round(wins.mean(), 2) if len(wins) else 0.0,
        "avg_loss_pips": round(losses.mean(), 2) if len(losses) else 0.0,
        "payoff_ratio": round(abs(wins.mean() / losses.mean()), 3)
                        if len(wins) and losses.mean() != 0 else None,
        "profit_factor": round(gp / gl, 3) if gl > 0 else None,
        "expectancy_pips": round(net.mean(), 3),
        "gross_total_pips": round(gross.sum(), 1),
        "cost_total_pips": round(cost_rt_pips * len(net), 1),
        "net_total_pips": round(net.sum(), 1),
        "net_total_usd_1lot": round(net.sum() * USD_PER_PIP, 2),
        "max_drawdown_pips": round(float(max_dd), 1),
        "max_drawdown_usd_1lot": round(float(max_dd) * USD_PER_PIP, 2),
        "sharpe": round(float(sharpe), 3),
        "calmar": round(net.sum() / abs(max_dd), 3) if max_dd < 0 else None,
        "avg_holding_bars": round(np.mean([t["bars_held"] for t in trades]), 2),
        "exposure": round(min(in_market / max(len(equity), 1), 1.0), 4),
        "exit_reasons": pd.Series([t["exit_reason"] for t in trades])
                          .value_counts().to_dict(),
    }


def load_data(path: Path, min_bars: int) -> tuple[pd.DataFrame, int]:
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    raw_n = len(df)
    df = df[df["bars"] >= min_bars].sort_values("date").reset_index(drop=True)
    return df, raw_n - len(df)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="EURUSD mean reversion backtest (V1 baseline + V2 trend gate)")
    ap.add_argument("--data", default=str(DEFAULT_DATA))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--window", type=int, default=20,
                    help="lookback days defining the range (default 20)")
    ap.add_argument("--eps", type=float, default=0.001,
                    help="touch tolerance around range edge, fraction (default 0.001)")
    ap.add_argument("--stop-atr", type=float, default=2.0,
                    help="stop distance in ATR multiples (default 2.0)")
    ap.add_argument("--max-hold", type=int, default=10,
                    help="time stop in bars (default 10)")
    ap.add_argument("--cost-rt-pips", type=float, default=1.5,
                    help="round-trip spread+commission in pips (default 1.5)")
    ap.add_argument("--min-bars", type=int, default=100,
                    help="drop days with fewer than this many M1 bars (default 100)")
    ap.add_argument("--adx-max", type=float, default=25.0,
                    help="V2 gate: take signals only when ADX below this "
                         "(default 25). Use a negative value to disable the "
                         "gate and reproduce V1 exactly.")
    ap.add_argument("--adx-period", type=int, default=14)
    ap.add_argument("--no-target", action="store_true",
                    help="disable take-profit at range mid (stop + time stop only)")
    args = ap.parse_args()

    adx_max = None if (args.adx_max is not None and args.adx_max < 0) else args.adx_max

    df, dropped = load_data(Path(args.data), args.min_bars)
    common = dict(eps=args.eps, max_hold=args.max_hold,
                  cost_rt_pips=args.cost_rt_pips,
                  take_target=not args.no_target, adx_period=args.adx_period)

    # Baseline: identical machinery, gate disabled == V1.
    b_f, b_trades, b_equity = run_case(
        df, window=args.window, stop_atr=args.stop_atr, adx_max=None, **common)
    # Headline: V2 with the regime gate.
    f, trades, equity = run_case(
        df, window=args.window, stop_atr=args.stop_atr, adx_max=adx_max, **common)

    bstats = summarise(b_trades, b_equity, cost_rt_pips=args.cost_rt_pips,
                       label="V1_baseline_no_gate")
    stats = summarise(trades, equity, cost_rt_pips=args.cost_rt_pips,
                      label="V2_adx_gate" if adx_max is not None else "V1_no_gate")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tag = "v2_adx%d" % int(adx_max) if adx_max is not None else "v1_nogate"
    trades_path = out / f"{tag}_trades.csv"
    pd.DataFrame(trades).to_csv(trades_path, index=False)
    equity_path = out / f"{tag}_equity.csv"
    pd.DataFrame({"date": pd.to_datetime(f["date"]).dt.strftime("%Y-%m-%d"),
                  "equity_pips": np.round(equity, 3)}).to_csv(equity_path, index=False)

    # ---- time segments: was the result made of one lucky stretch? ---------
    years = pd.to_datetime(f["date"]).dt.year
    segments = []
    for start in range(2000, 2026, 5):
        end = start + 4
        idx = np.where(((years >= start) & (years <= end)).to_numpy())[0]
        if len(idx) == 0:
            continue
        sub_tr = [t for t in trades if start <= int(t["entry_date"][:4]) <= end]
        sub_eq = equity[idx[0]:idx[-1] + 1] - equity[idx[0]]
        segments.append(summarise(sub_tr, sub_eq,
                                  cost_rt_pips=args.cost_rt_pips,
                                  label=f"{start}-{end}"))
    half_segments = []
    for label, before in (("2000-2012", True), ("2013-2026", False)):
        mask = (years < 2013) if before else (years >= 2013)
        idx = np.where(mask.to_numpy())[0]
        if len(idx) == 0:
            continue
        sub_tr = [t for t in trades
                  if (int(t["entry_date"][:4]) < 2013) == before]
        sub_eq = equity[idx[0]:idx[-1] + 1] - equity[idx[0]]
        half_segments.append(summarise(sub_tr, sub_eq,
                                       cost_rt_pips=args.cost_rt_pips,
                                       label=label))

    # ---- ADX sweep: is the threshold a plateau or a lucky notch? ----------
    adx_sweep = []
    for thr in (None, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0):
        _, tr2, eq2 = run_case(df, window=args.window, stop_atr=args.stop_atr,
                               adx_max=thr, **common)
        st = summarise(tr2, eq2, cost_rt_pips=args.cost_rt_pips,
                       label=f"adx_{'off' if thr is None else int(thr)}")
        adx_sweep.append({"adx_max": thr, "trade_count": st.get("trade_count"),
                          "win_rate": st.get("win_rate"),
                          "payoff_ratio": st.get("payoff_ratio"),
                          "profit_factor": st.get("profit_factor"),
                          "net_total_pips": st.get("net_total_pips"),
                          "max_drawdown_pips": st.get("max_drawdown_pips"),
                          "calmar": st.get("calmar"),
                          "gross_total_pips": st.get("gross_total_pips"),
                          "sharpe": st.get("sharpe")})

    # ---- small grid around the headline parameters ------------------------
    grid = []
    for w in (15, 20, 25, 30):
        for s in (2.0, 2.5, 3.0):
            _, tr3, eq3 = run_case(df, window=w, stop_atr=s,
                                   adx_max=adx_max, **common)
            st = summarise(tr3, eq3, cost_rt_pips=args.cost_rt_pips,
                           label=f"w{w}_s{s}")
            grid.append({"window": w, "stop_atr": s,
                         "trade_count": st.get("trade_count"),
                         "win_rate": st.get("win_rate"),
                         "payoff_ratio": st.get("payoff_ratio"),
                         "profit_factor": st.get("profit_factor"),
                         "net_total_pips": st.get("net_total_pips"),
                         "max_drawdown_pips": st.get("max_drawdown_pips"),
                         "sharpe": st.get("sharpe")})

    report = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "data_path": str(args.data),
        "data_note": ("D1 derived from REAL HistData ASCII EURUSD M1 files; "
                      "8,999,733 M1 rows -> 8126 daily bars. "
                      "volume is identically 0 and is NOT used. "
                      "1 upstream spike bar (2001-06-07) already quarantined."),
        "bars_used": len(f),
        "bars_dropped_low_tick_count": dropped,
        "date_range": [str(pd.to_datetime(f['date']).min().date()),
                       str(pd.to_datetime(f['date']).max().date())],
        "params": {"window": args.window, "eps": args.eps,
                   "stop_atr": args.stop_atr, "max_hold": args.max_hold,
                   "cost_rt_pips": args.cost_rt_pips,
                   "min_bars": args.min_bars, "adx_max": adx_max,
                   "adx_period": args.adx_period,
                   "take_target_at_range_mid": not args.no_target},
        "assumptions": {
            "fill": "signal confirmed at bar close, filled at NEXT bar open",
            "stop_target_tie": "stop assumed hit first (conservative)",
            "cost": f"{args.cost_rt_pips} pips round trip (spread + commission)",
            "position": "one at a time, no pyramiding, no compounding, 1 lot",
            "usd_per_pip_1lot": USD_PER_PIP,
            "warmup": "baseline and gated runs drop identical warmup bars",
        },
        "v1_baseline": bstats,
        "headline": stats,
        "segments_5y": segments,
        "halves": half_segments,
        "adx_sweep": adx_sweep,
        "window_stop_grid": grid,
    }
    report_path = out / f"{tag}_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")

    # ---- console ---------------------------------------------------------
    p = report["params"]
    print("=" * 84)
    print("EURUSD MEAN REVERSION -- V1 baseline vs V2 trend gate (real data)")
    print("=" * 84)
    print(f"data   : {report['date_range'][0]} .. {report['date_range'][1]}  "
          f"({report['bars_used']} bars, identical window for every variant)")
    print(f"params : window={p['window']} eps={p['eps']} stop={p['stop_atr']}ATR "
          f"maxhold={p['max_hold']} cost={p['cost_rt_pips']}pip RT  "
          f"adx_max={p['adx_max']}")
    print("-" * 84)
    print(f"{'':<22}{'V1 no gate':>14}{'V2 adx gate':>14}")
    rows = [("trades", "trade_count", "{:.0f}"),
            ("win rate", "win_rate", "{:.1%}"),
            ("payoff ratio", "payoff_ratio", "{}"),
            ("profit factor", "profit_factor", "{}"),
            ("gross pips", "gross_total_pips", "{:+.1f}"),
            ("net pips", "net_total_pips", "{:+.1f}"),
            ("net USD 1 lot", "net_total_usd_1lot", "{:+,.0f}"),
            ("max DD USD 1 lot", "max_drawdown_usd_1lot", "{:,.0f}"),
            ("sharpe", "sharpe", "{}"),
            ("expectancy/trade", "expectancy_pips", "{:+.2f}")]
    for name, key, fmt in rows:
        a, b = bstats.get(key), stats.get(key)
        fa = fmt.format(a) if a is not None else "-"
        fb = fmt.format(b) if b is not None else "-"
        print(f"{name:<22}{fa:>14}{fb:>14}")
    print("-" * 84)
    print("ADX THRESHOLD SWEEP (plateau or lucky notch?)")
    print(f"  {'ADX<':<8}{'n':<6}{'win%':<8}{'payoff':<9}{'PF':<8}"
          f"{'gross':>9}{'net pips':>11}{'maxDD':>10}{'Sharpe':>8}")
    for r in adx_sweep:
        thr = "off" if r["adx_max"] is None else f"<{int(r['adx_max'])}"
        print(f"  {thr:<8}{r['trade_count']:<6}{r['win_rate']:.1%}    "
              f"{str(r['payoff_ratio']):<9}{str(r['profit_factor']):<8}"
              f"{r['gross_total_pips']:>+9.0f}{r['net_total_pips']:>+11.0f}"
              f"{r['max_drawdown_pips']:>+10.0f}{r['sharpe']:>8}")
    print("-" * 84)
    print("5-YEAR SEGMENTS (V2 gated)")
    for s in segments:
        print(f"  {s['label']}: n={s['trade_count']:<4} win={s.get('win_rate', 0):.1%} "
              f"pf={str(s.get('profit_factor')):<6} net={s.get('net_total_pips'):+8.1f}p "
              f"dd={s.get('max_drawdown_pips'):+8.1f}p")
    print("HALVES (V2 gated)")
    for s in half_segments:
        print(f"  {s['label']:<10}: n={s['trade_count']:<4} win={s.get('win_rate', 0):.1%} "
              f"pf={str(s.get('profit_factor')):<6} net={s.get('net_total_pips'):+8.1f}p")
    print("-" * 84)
    print("WINDOW x STOP GRID (V2 gated)")
    print(f"  {'w/s':<10}{'n':<6}{'win%':<8}{'payoff':<9}{'PF':<8}{'net pips':>11}{'Sharpe':>8}")
    for r in grid:
        print(f"  {r['window']}/{r['stop_atr']:<8}{r['trade_count']:<6}"
              f"{r['win_rate']:.1%}    {str(r['payoff_ratio']):<9}"
              f"{str(r['profit_factor']):<8}{r['net_total_pips']:>+11.0f}"
              f"{r['sharpe']:>8}")
    print("=" * 84)
    print(f"report -> {report_path}")
    print(f"trades -> {trades_path} ({len(trades)} rows)")
    print(f"equity -> {equity_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
