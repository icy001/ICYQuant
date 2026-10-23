"""Phase 8 - Research Layer: Factor Paper-Trading Gate (Alpha021).

First factor-track candidate wired into the deployed stack.  Alpha021 is
the only alpha that passed the 16-item Factor Gate on BOTH the synthetic
1H data (factor-v1) and the real daily data (factor-real-d1, gate-passed
assets NVDA / QQQ / SPY), and it survived the De-correlation Gate as its
own family (factor-real-cluster).  This gate verifies the full
factor -> signal -> paper-execution chain:

    real daily data (data/real/d1, akshare)
        -> Alpha021 (research.discovery.factor.formulas)
        -> rolling z-score (120 bars, sealed REAL_D1 windows)
        -> Schmitt-trigger positions
        -> orientation by the TRAIN IC sign (train-only decision)
        -> position changes -> paper trading signals
        -> PaperTradingSession (fill / reject / error / latency / slippage)

Long-only paper mapping (documented limitation): the paper account cannot
short, so +1 -> hold 100 shares, anything else -> flat.  A position change
across +1 emits BUY/SELL 100.

Usage (host or container; sync data/real/d1 into the container first):
    python -m apps.runtime factor [--json]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

from research.data.csv_provider import CsvMarketDataProvider
from research.data.types import TimeFrame
from research.discovery.factor.evaluation import segment_ic
from research.discovery.factor.factor_backtest import (
    orient_positions,
    positions_from_z,
    rolling_zscore,
)
from research.discovery.factor.factor_spec import FACTOR_SPEC_REAL_D1
from research.discovery.factor.formulas import MarketData, compute_alpha
from research.discovery.factor.operators import set_rank_window
from research.discovery.split import build_split

GATE_ID = "factor"
GATE_TITLE = "Factor Gate - Alpha021 paper trading (real daily data)"
ALPHA_ID = "Alpha021"
SYMBOLS = ("NVDA", "QQQ", "SPY")   # gate-passed assets on the real data
QUANTITY = 100                     # shares per paper position
MIN_BARS = 300                     # daily bars required per asset
MIN_COVERAGE = 0.75                # computable factor fraction
MIN_SIGNALS = 10                   # position changes expected in 2.6y


def data_dir() -> Path:
    """Resolve the real-data directory (host or container path)."""
    override = os.getenv("ICYQUANT_REAL_DATA_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "data" / "real" / "d1"


def build_signals(symbols: tuple[str, ...] = SYMBOLS) -> tuple[list, dict]:
    """Compute Alpha021 paper signals across the given assets.

    Returns ``(signals, context)`` where signals are paper-ready
    ``(symbol, side, quantity, ref_price, date)`` tuples and context holds
    per-asset diagnostics (bars, coverage, orientation, non-flat fraction),
    plus raw z-score and position series for chart rendering.
    """
    spec = FACTOR_SPEC_REAL_D1
    split = build_split(spec.split)
    set_rank_window(spec.rank_window or 120)
    provider = CsvMarketDataProvider(data_dir())

    signals: list[tuple] = []
    context: dict = {"assets": {}}
    for symbol in symbols:
        bars = provider.load_bars(symbol, TimeFrame.D1)
        md = MarketData(
            open_=[b.open for b in bars],
            high=[b.high for b in bars],
            low=[b.low for b in bars],
            close=[b.close for b in bars],
            volume=[b.volume for b in bars],
        )
        factor = compute_alpha(ALPHA_ID, md)
        n = len(factor)
        coverage = sum(1 for v in factor if v is not None and v == v) / n if n else 0.0

        dates = [b.timestamp.date() for b in bars]
        bar_returns: list = [None] * n
        for i in range(1, n):
            if md.close[i - 1] not in (None, 0) and md.close[i] is not None:
                bar_returns[i] = md.close[i] / md.close[i - 1] - 1.0

        train_idx = [i for i, d in enumerate(dates)
                     if split.train_start <= d <= split.train_end]
        train_ic = segment_ic(factor, bar_returns, train_idx,
                              block_bars=spec.ic_block_bars or 60).ic
        z = rolling_zscore(factor, window=spec.z_window or 120)
        positions, orientation = orient_positions(positions_from_z(z), train_ic)

        n_changes = 0
        for t in range(1, n):
            prev, cur = positions[t - 1], positions[t]
            if prev == cur:
                continue
            n_changes += 1
            # long-only paper mapping: BUY entering +1, SELL leaving +1
            if cur == 1.0 and prev != 1.0:
                signals.append((symbol, "BUY", QUANTITY,
                                md.close[t], dates[t].isoformat()))
            elif prev == 1.0 and cur != 1.0:
                signals.append((symbol, "SELL", QUANTITY,
                                md.close[t], dates[t].isoformat()))

        non_flat = sum(1 for p in positions if p != 0.0)
        # store raw series for chart rendering
        z_clean = [round(v, 4) if (v is not None and v == v) else None for v in z]
        pos_clean = [round(p, 4) for p in positions]
        context["assets"][symbol] = {
            "bars": n,
            "coverage": round(coverage, 4),
            "orientation": orientation,
            "train_ic": train_ic,
            "non_flat_frac": round(non_flat / n, 4) if n else 0.0,
            "position_changes": n_changes,
            "last_close": md.close[-1] if md.close else None,
            "dates": [d.isoformat() for d in dates],
            "closes": [round(c, 4) if c is not None else None for c in md.close],
            "z_scores": z_clean,
            "positions": pos_clean,
        }

    # chronological order, deterministic within a day
    signals.sort(key=lambda s: (s[4], s[0]))
    context["signals_total"] = len(signals)
    return signals, context


# --------------------------------------------------------------------------- #
# Extended metrics & chart helpers (for the Product UI)                        #
# --------------------------------------------------------------------------- #

def _compute_extended_metrics(eq_vals: list, closed: list,
                              initial_capital: float) -> dict:
    """Compute CAGR, Sortino, Calmar from the daily equity curve + closed trades."""
    if not eq_vals or len(eq_vals) < 2:
        return {"cagr": None, "sortino": None, "calmar": None,
                "avg_win": None, "avg_loss": None,
                "profit_factor": None, "expectancy": None,
                "avg_holding_days": None, "best_trade": None, "worst_trade": None}

    # CAGR
    days = len(eq_vals)
    if days >= 2:
        total_years = days / 252.0
        cagr = ((eq_vals[-1] / initial_capital) ** (1.0 / total_years) - 1.0) * 100
    else:
        cagr = None

    # Daily returns
    rets = [(eq_vals[i] / eq_vals[i - 1] - 1.0)
            for i in range(1, len(eq_vals)) if eq_vals[i - 1] > 0]

    # Sortino (downside deviation)
    if len(rets) >= 3:
        mean_ret = sum(rets) / len(rets)
        downside = [r for r in rets if r < 0]
        if downside:
            downside_var = sum((r ** 2) for r in downside) / len(downside)
            downside_std = downside_var ** 0.5
            if downside_std > 0:
                sortino = round(mean_ret / downside_std * (252 ** 0.5), 2)
            else:
                sortino = None
        else:
            sortino = None
    else:
        sortino = None

    # Calmar
    peak = eq_vals[0]
    maxdd = 0.0
    for v in eq_vals:
        peak = max(peak, v)
        maxdd = min(maxdd, v / peak - 1.0)
    ann_ret = (eq_vals[-1] / initial_capital - 1.0) * 100
    calmar = round(ann_ret / abs(maxdd * 100), 2) if maxdd < 0 else None

    # Trade analysis
    wins = [r for r in closed if r["realized_pnl"] > 0]
    losses = [r for r in closed if r["realized_pnl"] <= 0]
    gross_profit = sum(r["realized_pnl"] for r in wins)
    gross_loss = abs(sum(r["realized_pnl"] for r in losses))

    avg_win = round(gross_profit / len(wins), 2) if wins else None
    avg_loss = round(-gross_loss / len(losses), 2) if losses else None
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None
    total_trades = len(wins) + len(losses)
    expectancy = round(
        (gross_profit / total_trades if total_trades else 0) +
        (gross_loss / total_trades if total_trades else 0), 2
    ) if total_trades else None

    best_trade = max((r["realized_pnl"] for r in closed), default=None)
    worst_trade = min((r["realized_pnl"] for r in closed), default=None)

    # Average holding period (all trades assumed T+0 for daily data -> 1 day)
    avg_holding = 1  # daily data, all trades are same-day resolution

    return {
        "cagr": round(cagr, 2) if cagr is not None else None,
        "sortino": sortino,
        "calmar": calmar,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "avg_holding_days": avg_holding,
        "best_trade": round(best_trade, 2) if best_trade is not None else None,
        "worst_trade": round(worst_trade, 2) if worst_trade is not None else None,
    }


def _compute_drawdown_series(eq_vals: list) -> list:
    """Compute the drawdown series (percentage from peak) for each day."""
    if not eq_vals:
        return []
    peak = eq_vals[0]
    dd = []
    for v in eq_vals:
        peak = max(peak, v)
        dd.append(round((v / peak - 1.0) * 100, 4))
    return dd


def _compute_monthly_returns(eq_rows: list) -> list:
    """Compute monthly return heatmap data: [{month, return_pct}]."""
    if len(eq_rows) < 2:
        return []
    monthly = {}
    for row in eq_rows:
        date = row["date"]  # "YYYY-MM-DD"
        month_key = date[:7]  # "YYYY-MM"
        monthly[month_key] = row["equity"]

    sorted_months = sorted(monthly.keys())
    returns = []
    for i in range(1, len(sorted_months)):
        prev_eq = monthly[sorted_months[i - 1]]
        cur_eq = monthly[sorted_months[i]]
        if prev_eq > 0:
            ret = round((cur_eq / prev_eq - 1.0) * 100, 2)
            returns.append({"month": sorted_months[i], "return_pct": ret})
    return returns


def _build_chart_data(context: dict, symbols: tuple[str, ...],
                      eq_rows: list, trades: list) -> list:
    """Build per-symbol daily chart data with price, z-score, position.

    Returns a list of chart panels, one per symbol. Each panel has:
      symbol, dates[], closes[], z_scores[], positions[],
      signals[] (BUY/SELL markers), equity_line[] (portfolio equity).
    """
    panels = []
    # Build equity lookup by date
    eq_by_date = {r["date"]: r["equity"] for r in eq_rows}
    # Build signal markers by symbol+date
    signals_by_sym_date: dict[str, dict[str, list]] = {}
    for t in trades:
        if t["outcome"] == "FILLED":
            signals_by_sym_date.setdefault(t["symbol"], {}).setdefault(
                t["date"], []).append({
                "side": t["side"], "price": t["exec_price"],
                "seq": t["seq"],
            })

    for sym in symbols:
        asset = context["assets"].get(sym, {})
        dates = asset.get("dates", [])
        closes = asset.get("closes", [])
        z_scores = asset.get("z_scores", [])
        positions = asset.get("positions", [])

        n = len(dates)
        chart = {
            "symbol": sym,
            "dates": dates,
            "closes": closes,
            "z_scores": z_scores,
            "positions": positions,
            "signals": [],
            "equity_line": [],
        }
        # Signal markers
        for d in dates:
            sigs = signals_by_sym_date.get(sym, {}).get(d, [])
            if sigs:
                chart["signals"].extend(sigs)
        # Portfolio equity aligned to dates
        for d in dates:
            chart["equity_line"].append(eq_by_date.get(d))

        panels.append(chart)
    return panels


# --------------------------------------------------------------------------- #
# Paper-trading log export                                                     #
# --------------------------------------------------------------------------- #
def _replay(signals: list, context: dict, symbols: tuple[str, ...],
            start: Optional[str], end: Optional[str],
            initial_capital: float) -> dict:
    """Deterministic replay core shared by the gate, snapshots and the
    product Backtest page.

    Reuses the FROZEN factor components (compute_alpha -> z-score ->
    Schmitt trigger -> train-IC orientation from the sealed REAL_D1
    split); only the replay window, universe and initial capital are
    parameterised.  Price accounting is marked to the REAL world:
    exec = real close * (1 +/- 3 bps).

    Returns ``{meta, trades, equity, summary}``.
    """
    from apps.runtime.paper_trading import (
        PaperAccount,
        PaperTradingSession,
        SignalSpec,
        SimulatedMarketFeed,
    )

    assets = context["assets"]
    base_prices = {s: a["last_close"] or 100.0
                   for s, a in assets.items() if a.get("last_close")}
    session = PaperTradingSession(
        feed=SimulatedMarketFeed(base_prices=base_prices, seed=42),
        account=PaperAccount(initial_cash=initial_capital))
    bps = session.slippage_bps / 1e4

    # window filter (None = unbounded, identical to the sealed replay)
    flt = [s for s in signals
           if (start is None or s[4] >= start) and (end is None or s[4] <= end)]

    book: dict[str, dict] = {}
    cum_realized = 0.0
    rows: list[dict] = []
    fills: list[tuple] = []   # (date, symbol, side, eff_qty, exec_price)

    for seq, (symbol, side, qty, ref, date) in enumerate(flt, 1):
        rec = session.process(
            SignalSpec(symbol=symbol, side=side, quantity=qty, ref_price=ref))
        latency = rec.get("latency_total_us")
        if rec.get("error"):
            outcome = "ERROR"
        elif rec.get("rejected"):
            outcome = "REJECTED"
        else:
            outcome = "FILLED"

        exec_price = None
        if outcome == "FILLED":
            exec_price = ref * (1.0 + bps) if side == "BUY" \
                else ref * (1.0 - bps)

        p = book.setdefault(symbol, {"qty": 0, "avg_cost": 0.0})
        realized = 0.0
        eff_qty = 0
        if outcome == "FILLED" and exec_price is not None:
            if side == "BUY":
                eff_qty = qty
                new_qty = p["qty"] + qty
                p["avg_cost"] = ((p["avg_cost"] * p["qty"]
                                  + exec_price * qty) / new_qty)
                p["qty"] = new_qty
            else:
                eff_qty = min(qty, p["qty"])   # long-only: close what's held
                if eff_qty:
                    realized = (exec_price - p["avg_cost"]) * eff_qty
                    p["qty"] -= eff_qty
                    cum_realized += realized
            fills.append((date, symbol, side, eff_qty, exec_price))
        rows.append({
            "seq": seq,
            "date": date,
            "symbol": symbol,
            "side": side,
            "quantity": qty,
            "ref_price_real_close": round(ref, 4),
            "outcome": outcome,
            "exec_price": round(exec_price, 4) if exec_price else "",
            "slippage_bps": (bps * 1e4 if exec_price else ""),
            "latency_total_us": round(latency, 1) if latency is not None else "",
            "filled_quantity": eff_qty,
            "position_after": p["qty"],
            "avg_cost_after": round(p["avg_cost"], 4),
            "realized_pnl": round(realized, 2),
            "cum_realized_pnl": round(cum_realized, 2),
        })

    # ---- daily equity curve marked to the real closes ------------------ #
    closes: dict[str, dict[str, float]] = {}
    provider = CsvMarketDataProvider(data_dir())
    for s in symbols:
        bars = provider.load_bars(s, TimeFrame.D1)
        closes[s] = {b.timestamp.date().isoformat(): b.close for b in bars}
    fill_days = sorted({f[0] for f in fills})
    all_days = sorted({d for s in symbols for d in closes[s]})
    days = [d for d in all_days if fill_days[0] <= d <= fill_days[-1]]
    fills_by_day: dict[str, list[tuple]] = {}
    for f in fills:
        fills_by_day.setdefault(f[0], []).append(f)

    eq_rows: list[dict] = []
    pos_qty = {s: 0 for s in symbols}
    cash_eq = float(initial_capital)
    last_close: dict[str, float] = {}
    for d in days:
        for s in symbols:
            if d in closes[s]:
                last_close[s] = closes[s][d]
        for (_d, s, side, q, px) in fills_by_day.get(d, []):
            if side == "BUY":
                cash_eq -= q * px
                pos_qty[s] += q
            else:
                cash_eq += q * px
                pos_qty[s] -= q
        value = sum(pos_qty[s] * last_close.get(s, 0.0)
                    for s in symbols if pos_qty[s])
        eq_rows.append({
            "date": d,
            "cash": round(cash_eq, 2),
            "positions_value": round(value, 2),
            "equity": round(cash_eq + value, 2),
            "held": " ".join(f"{s}:{pos_qty[s]}" for s in symbols
                             if pos_qty[s]) or "flat",
        })

    # ---- per-symbol summary -------------------------------------------- #
    sum_rows: list[dict] = []
    for s in symbols:
        rs = [r for r in rows if r["symbol"] == s]
        filled = [r for r in rs if r["outcome"] == "FILLED"]
        p = book.get(s, {"qty": 0, "avg_cost": 0.0})
        last = assets[s].get("last_close")
        unreal = ((last - p["avg_cost"]) * p["qty"]
                  if last and p["qty"] else 0.0)
        sum_rows.append({
            "symbol": s,
            "signals": len(rs),
            "filled": len(filled),
            "rejected": sum(1 for r in rs if r["outcome"] == "REJECTED"),
            "errored": sum(1 for r in rs if r["outcome"] == "ERROR"),
            "realized_pnl": round(sum(r["realized_pnl"] for r in rs), 2),
            "final_position": p["qty"],
            "avg_cost": round(p["avg_cost"], 4),
            "last_close": last,
            "unrealized_pnl": round(unreal, 2),
        })
    total_realized = round(sum(r["realized_pnl"] for r in rows), 2)
    sum_rows.append({
        "symbol": "TOTAL", "signals": len(rows),
        "filled": sum(1 for r in rows if r["outcome"] == "FILLED"),
        "rejected": sum(1 for r in rows if r["outcome"] == "REJECTED"),
        "errored": sum(1 for r in rows if r["outcome"] == "ERROR"),
        "realized_pnl": total_realized, "final_position": "",
        "avg_cost": "", "last_close": "",
        "unrealized_pnl": round(sum(r["unrealized_pnl"] for r in sum_rows), 2),
    })

    # ---- headline metrics ----------------------------------------------- #
    closed = [r for r in rows if r["side"] == "SELL"
              and r["outcome"] == "FILLED" and r["realized_pnl"]]
    wins = [r for r in closed if r["realized_pnl"] > 0]
    eq_vals = [r["equity"] for r in eq_rows]
    maxdd = 0.0
    if eq_vals:
        peak = eq_vals[0]
        for v in eq_vals:
            peak = max(peak, v)
            maxdd = min(maxdd, v / peak - 1.0)
    # annualised Sharpe on daily equity returns
    sharpe = None
    if len(eq_vals) >= 3:
        rets = [(eq_vals[i] / eq_vals[i - 1] - 1.0)
                for i in range(1, len(eq_vals)) if eq_vals[i - 1] > 0]
        if len(rets) >= 3:
            mean = sum(rets) / len(rets)
            var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
            std = var ** 0.5
            if std > 0:
                sharpe = round(mean / std * (252 ** 0.5), 2)
    turnover = (round(sum(f[3] for f in fills) / len(eq_rows), 2)
                if eq_rows else 0.0)

    # Extended metrics (CAGR, Sortino, Calmar, trade analysis)
    ext = _compute_extended_metrics(eq_vals, closed, initial_capital)
    drawdown_series = _compute_drawdown_series(eq_vals)
    monthly_returns = _compute_monthly_returns(eq_rows)

    meta = {
        "alpha_id": ALPHA_ID,
        "symbols": list(symbols),
        "period": f"{rows[0]['date']} → {rows[-1]['date']}" if rows else "",
        "initial_capital": float(initial_capital),
        "realized": total_realized,
        "unrealized": sum_rows[-1]["unrealized_pnl"],
        "equity_final": eq_rows[-1]["equity"] if eq_rows else None,
        "return_pct": ((eq_vals[-1] / initial_capital - 1.0) * 100
                       if eq_vals else 0.0),
        "maxdd_pct": maxdd * 100,
        "sharpe": sharpe,
        "turnover_shares_per_day": turnover,
        "signals": len(rows),
        "filled": sum(1 for r in rows if r["outcome"] == "FILLED"),
        "rejected": sum(1 for r in rows if r["outcome"] == "REJECTED"),
        "errored": sum(1 for r in rows if r["outcome"] == "ERROR"),
        "closed_trips": len(closed),
        "win_rate": (100.0 * len(wins) / len(closed)) if closed else 0.0,
        # Extended metrics
        "cagr": ext["cagr"],
        "sortino": ext["sortino"],
        "calmar": ext["calmar"],
        "avg_win": ext["avg_win"],
        "avg_loss": ext["avg_loss"],
        "profit_factor": ext["profit_factor"],
        "expectancy": ext["expectancy"],
        "avg_holding_days": ext["avg_holding_days"],
        "best_trade": ext["best_trade"],
        "worst_trade": ext["worst_trade"],
    }

    # Chart data: per-symbol price/z/position + signal markers
    chart_panels = _build_chart_data(context, symbols, eq_rows, rows)

    return {
        "meta": meta,
        "trades": rows,
        "equity": eq_rows,
        "summary": sum_rows,
        "drawdown_series": drawdown_series,
        "monthly_returns": monthly_returns,
        "chart_panels": chart_panels,
    }


# assets with real daily data available for the Backtest page (the full
# research universe; Alpha021 gate-passed only NVDA/QQQ/SPY)
BACKTEST_UNIVERSE = ("NVDA", "QQQ", "SPY", "000688.SH", "HSTECH",
                     "EURUSD", "XAUUSD", "AU", "AG")


def run_backtest(symbols: Optional[list[str]] = None,
                 start: Optional[str] = None, end: Optional[str] = None,
                 initial_capital: float = 1_000_000.0) -> dict:
    """Parameterised Alpha021 backtest for the product Backtest page.

    Product-layer wrapper around the frozen factor components: the replay
    window, universe and capital are caller-supplied; the quant logic
    (formula, windows, orientation) stays exactly as sealed in
    FACTOR_SPEC_REAL_D1 (Factor Discovery v2 — CLOSED).
    """
    root = data_dir()
    syms = tuple(symbols) if symbols else SYMBOLS
    invalid = [s for s in syms if s not in BACKTEST_UNIVERSE]
    if invalid:
        raise ValueError(f"unknown symbols: {', '.join(invalid)}")
    missing = [s for s in syms if not (root / f"{s}_1d.csv").exists()]
    if missing:
        raise FileNotFoundError(
            f"no real daily data for: {', '.join(missing)}")
    signals, context = build_signals(syms)
    return _replay(signals, context, syms, start, end, initial_capital)


def build_paper_data() -> dict:
    """Deterministic Alpha021 paper run -> full data payload (no IO).

    Shared by the CSV/HTML export and the Dashboard API.  Returns
    ``{meta, trades, equity, summary}`` where equity/summary/meta match the
    exported CSV schemas.  Raises on missing data files (callers decide how
    to surface that).
    """
    signals, context = build_signals()
    return _replay(signals, context, SYMBOLS, None, None, 1_000_000.0)


def export_paper_log(out_dir: Path) -> dict:
    """Run the deterministic Alpha021 paper session and dump the full logs.

    Same seed and signal order as the gate run, so broker outcomes (fill /
    reject / error, latency) are identical.  **Price accounting is marked
    to the REAL world** (documented deviation from the session's internal
    random-walk feed, which exists for pipeline plumbing validation only):

    - exec price = real close * (1 ± session.slippage_bps), i.e. a fixed
      3 bps friction each way;
    - long-only book: BUY adds, SELL closes at most what is held (a
      rejected SELL leaves the position open — surfaced as position
      drift in the summary, an honest artifact of broker rejections).

    Writes four files under ``out_dir``:

    - ``trades.csv``        — one row per signal: date / symbol / side /
      real close / outcome / exec price / latency / position after /
      per-trade realized PnL
    - ``equity_curve.csv``  — daily cash / positions value / equity marked
      to the REAL closing prices
    - ``summary.csv``       — per-symbol and total fills, rejections,
      realized / unrealized PnL, final (drifted) position
    - ``report.html``       — self-contained web page (charts + tables)
    """
    data = build_paper_data()
    rows, eq_rows, sum_rows = data["trades"], data["equity"], data["summary"]
    meta = data["meta"]
    total_realized = meta["realized"]

    out_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(out_dir / "trades.csv", rows)
    _write_csv(out_dir / "equity_curve.csv", eq_rows)
    _write_csv(out_dir / "summary.csv", sum_rows)
    (out_dir / "report.html").write_text(
        _html_report(rows, eq_rows, sum_rows, meta), encoding="utf-8")

    return {"out_dir": out_dir, "signals": len(rows),
            "realized_pnl": total_realized,
            "equity_final": eq_rows[-1]["equity"] if eq_rows else None}


def _write_csv(path: Path, rows: list[dict]) -> None:
    import csv
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__ALPHA__ Paper Trading 报告</title>
<style>
  :root { --bg:#0d1117; --card:#161b22; --border:#30363d; --fg:#e6edf3;
          --muted:#8b949e; --green:#3fb950; --red:#f85149; --blue:#58a6ff; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--fg);
         font:14px/1.5 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
         padding:24px; }
  h1 { font-size:20px; margin-bottom:4px; }
  .sub { color:var(--muted); margin-bottom:20px; font-size:13px; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
           gap:12px; margin-bottom:20px; }
  .card { background:var(--card); border:1px solid var(--border);
          border-radius:8px; padding:12px 14px; }
  .card .k { color:var(--muted); font-size:12px; }
  .card .v { font-size:19px; font-weight:600; margin-top:2px; }
  .pos { color:var(--green); } .neg { color:var(--red); }
  .panel { background:var(--card); border:1px solid var(--border);
           border-radius:8px; padding:16px; margin-bottom:20px; }
  .panel h2 { font-size:15px; margin-bottom:12px; }
  svg { width:100%; height:auto; display:block; }
  .filters { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px; }
  .filters button { background:#21262d; color:var(--fg); border:1px solid var(--border);
                    border-radius:6px; padding:4px 12px; cursor:pointer; font-size:13px; }
  .filters button.active { background:#1f6feb; border-color:#1f6feb; }
  table { width:100%; border-collapse:collapse; font-size:12.5px; }
  th, td { padding:6px 8px; text-align:right; border-bottom:1px solid var(--border);
           white-space:nowrap; }
  th { color:var(--muted); font-weight:500; cursor:pointer; user-select:none; }
  th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) { text-align:left; }
  tr:hover td { background:#1c2129; }
  .tag { padding:1px 8px; border-radius:10px; font-size:11px; }
  .tag.FILLED { background:#0f3a1c; color:var(--green); }
  .tag.REJECTED { background:#4a2900; color:#d29922; }
  .tag.ERROR { background:#4a1212; color:var(--red); }
  .foot { color:var(--muted); font-size:12px; margin-top:8px; }
  #tip { position:fixed; display:none; background:#21262d; border:1px solid var(--border);
         border-radius:6px; padding:6px 10px; font-size:12px; pointer-events:none; }
</style>
</head>
<body>
<h1>__ALPHA__ · Paper Trading 报告</h1>
<div class="sub">__SYMBOLS__ · 真实日频数据 · __PERIOD__ · 定价：真实收盘 ± 3 bps · 初始资金 $1,000,000</div>
<div class="cards" id="cards"></div>
<div class="panel"><h2>净值曲线（按真实收盘 mark-to-market）</h2><div id="eqchart"></div></div>
<div class="panel"><h2>累计已实现盈亏（逐笔平仓）</h2><div id="pnlchart"></div></div>
<div class="panel"><h2>分资产汇总</h2><div id="sumtable"></div></div>
<div class="panel"><h2>交易明细</h2>
  <div class="filters" id="filters"></div>
  <div style="overflow:auto; max-height:520px"><table id="tradestable"></table></div>
</div>
<div class="foot">多头纸面映射：+1 → 100 股，其余空仓；拒单会导致仓位漂移（期末未平仓位见汇总表）。
生成的 CSV 与本页同目录：trades.csv / equity_curve.csv / summary.csv。</div>
<div id="tip"></div>
<script>
const DATA = __DATA__;
const fmt$ = v => (v<0?'-$':'$') + Math.abs(v).toLocaleString('en-US',{maximumFractionDigits:0});
const fmt2 = v => (v<0?'-$':'$') + Math.abs(v).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const m = DATA.meta;

// ---- cards ----
const cards = [
  ['期末净值', fmt$(m.equity_final), ''],
  ['总收益率', m.return_pct.toFixed(2)+'%', m.return_pct>=0?'pos':'neg'],
  ['已实现盈亏', fmt2(m.realized), m.realized>=0?'pos':'neg'],
  ['浮动盈亏', fmt2(m.unrealized), m.unrealized>=0?'pos':'neg'],
  ['最大回撤', m.maxdd_pct.toFixed(1)+'%', 'neg'],
  ['平仓笔数 / 胜率', m.closed_trips+' 笔 / '+m.win_rate.toFixed(0)+'%', ''],
  ['信号 / 成交', m.signals+' / '+m.filled, ''],
  ['拒单 / 错误', m.rejected+' / '+m.errored, ''],
];
document.getElementById('cards').innerHTML = cards.map(c =>
  `<div class="card"><div class="k">${c[0]}</div><div class="v ${c[2]}">${c[1]}</div></div>`).join('');

// ---- generic line chart (SVG) ----
function lineChart(el, pts, opts) {
  // pts: [{x(label), y}], opts: {color, fmt, baseline}
  const W=920, H=260, P=52;
  const ys = pts.map(p=>p.y), bl = opts.baseline;
  let lo = Math.min(...ys, bl), hi = Math.max(...ys, bl);
  const pad = (hi-lo)*0.08 || 1; lo-=pad; hi+=pad;
  const X = i => P + i*(W-2*P)/Math.max(pts.length-1,1);
  const Y = v => H-P - (v-lo)*(H-2*P)/(hi-lo);
  let s = `<svg viewBox="0 0 ${W} ${H}">`;
  // gridlines + y labels
  for (let g=0; g<=4; g++) {
    const v = lo + g*(hi-lo)/4, y = Y(v);
    s += `<line x1="${P}" y1="${y}" x2="${W-P}" y2="${y}" stroke="#21262d"/>`
       + `<text x="${P-6}" y="${y+4}" fill="#8b949e" font-size="11" text-anchor="end">${opts.fmt(v)}</text>`;
  }
  if (bl>lo && bl<hi) s += `<line x1="${P}" y1="${Y(bl)}" x2="${W-P}" y2="${Y(bl)}" stroke="#30363d" stroke-dasharray="4 4"/>`;
  const path = pts.map((p,i)=>(i?'L':'M')+X(i).toFixed(1)+' '+Y(p.y).toFixed(1)).join(' ');
  s += `<path d="${path}" fill="none" stroke="${opts.color}" stroke-width="1.8"/>`;
  // x labels: first / mid / last
  [0, Math.floor(pts.length/2), pts.length-1].forEach(i=>{
    s += `<text x="${X(i)}" y="${H-P+16}" fill="#8b949e" font-size="11" text-anchor="middle">${pts[i].x}</text>`;});
  // hover
  s += `<line id="cross" x1="0" y1="${P}" x2="0" y2="${H-P}" stroke="#58a6ff" stroke-width="0.6" opacity="0"/>`;
  s += `<rect id="hit" x="${P}" y="${P}" width="${W-2*P}" height="${H-2*P}" fill="transparent"/>`;
  s += `</svg>`;
  el.innerHTML = s;
  const svg = el.firstChild, cross = svg.querySelector('#cross'),
        tip = document.getElementById('tip');
  svg.querySelector('#hit').addEventListener('mousemove', e => {
    const r = svg.getBoundingClientRect(), sx = W/r.width;
    const i = Math.max(0, Math.min(pts.length-1,
      Math.round(((e.clientX-r.left)*sx - P)/((W-2*P)/Math.max(pts.length-1,1)))));
    cross.setAttribute('x1', X(i)); cross.setAttribute('x2', X(i));
    cross.setAttribute('opacity','0.6');
    tip.style.display='block';
    tip.style.left=(e.clientX+14)+'px'; tip.style.top=(e.clientY-10)+'px';
    tip.innerHTML = `<b>${pts[i].x}</b> · ${opts.fmt(pts[i].y)}`;
  });
  svg.addEventListener('mouseleave', ()=>{ cross.setAttribute('opacity','0');
    tip.style.display='none'; });
}

lineChart(document.getElementById('eqchart'),
  DATA.equity.map(r=>({x:r.date, y:r.equity})),
  {color:'#58a6ff', baseline:1000000, fmt:v=>'$'+(v/1000).toFixed(0)+'k'});

lineChart(document.getElementById('pnlchart'),
  DATA.trades.filter(r=>r.outcome==='FILLED').map(r=>({x:r.date, y:r.cum_realized_pnl})),
  {color:'#3fb950', baseline:0, fmt:v=>(v>=0?'+$':'-$')+Math.abs(v).toFixed(0)});

// ---- summary table ----
const sumCols = [['symbol','资产'],['signals','信号'],['filled','成交'],['rejected','拒单'],
  ['errored','错误'],['realized_pnl','已实现'],['final_position','期末仓位'],
  ['avg_cost','持仓成本'],['last_close','最新收盘'],['unrealized_pnl','浮动盈亏']];
document.getElementById('sumtable').innerHTML =
  '<table><tr>'+sumCols.map(c=>`<th>${c[1]}</th>`).join('')+'</tr>'
  + DATA.summary.map(r=>'<tr>'+sumCols.map(c=>{
      let v = r[c[0]];
      if (c[0]==='realized_pnl'||c[0]==='unrealized_pnl')
        v = `<span class="${v>=0?'pos':'neg'}">${fmt2(v)}</span>`;
      return `<td>${v}</td>`;}).join('')+'</tr>').join('')+'</table>';

// ---- trades table with filters ----
let fSym='ALL', fOut='ALL', sortKey='seq', sortDir=1;
const cols = [['seq','#'],['date','日期'],['symbol','资产'],['side','方向'],
  ['quantity','数量'],['ref_price_real_close','收盘价'],['outcome','结果'],
  ['exec_price','成交价'],['latency_total_us','延迟μs'],['filled_quantity','成交量'],
  ['position_after','仓位数'],['avg_cost_after','成本'],['realized_pnl','平仓盈亏'],
  ['cum_realized_pnl','累计盈亏']];
function render() {
  let rows = DATA.trades.filter(r =>
    (fSym==='ALL'||r.symbol===fSym) && (fOut==='ALL'||r.outcome===fOut));
  rows.sort((a,b)=>{const x=a[sortKey],y=b[sortKey];
    return (typeof x==='number'?x-y:String(x).localeCompare(String(y)))*sortDir;});
  document.querySelector('#tradestable').innerHTML =
    '<tr>'+cols.map(c=>`<th data-k="${c[0]}">${c[1]}${sortKey===c[0]?(sortDir>0?' ▲':' ▼'):''}</th>`).join('')+'</tr>'
    + rows.map(r=>'<tr>'+cols.map(c=>{
        let v = r[c[0]];
        if (c[0]==='outcome') v = `<span class="tag ${v}">${v}</span>`;
        if (c[0]==='realized_pnl'&&v) v = `<span class="${v>=0?'pos':'neg'}">${fmt2(v)}</span>`;
        if (c[0]==='cum_realized_pnl') v = `<span class="${v>=0?'pos':'neg'}">${fmt$(v)}</span>`;
        return `<td>${v}</td>`;}).join('')+'</tr>').join('');
  document.querySelectorAll('#tradestable th').forEach(th =>
    th.onclick = () => { const k = th.dataset.k;
      if (sortKey===k) sortDir*=-1; else {sortKey=k; sortDir=1;} render(); });
}
const fl = document.getElementById('filters');
['ALL',...m.symbols].forEach(s => {
  const b = document.createElement('button'); b.textContent = s;
  b.onclick = () => { fSym=s; fl.querySelectorAll('button').forEach(x=>x.classList.remove('active'));
    b.classList.add('active'); render(); };
  if (s==='ALL') b.classList.add('active'); fl.appendChild(b); });
['ALL','FILLED','REJECTED','ERROR'].forEach(o => {
  const b = document.createElement('button'); b.textContent = o;
  b.onclick = () => { fOut=o; render(); }; fl.appendChild(b); });
render();
</script>
</body>
</html>
"""


def _html_report(rows: list[dict], eq_rows: list[dict],
                 sum_rows: list[dict], meta: dict) -> str:
    """Self-contained HTML page: cards + SVG charts + filterable tables."""
    import json
    data = {"meta": meta, "trades": rows, "equity": eq_rows,
            "summary": sum_rows}
    return (_HTML_TEMPLATE
            .replace("__ALPHA__", meta["alpha_id"])
            .replace("__SYMBOLS__", " / ".join(meta["symbols"]))
            .replace("__PERIOD__", meta["period"])
            .replace("__DATA__", json.dumps(data, ensure_ascii=False)))


def run_factor_gate() -> dict:
    """Run the end-to-end Alpha021 factor -> paper chain and check results."""
    checks: list[dict] = []
    detail_lines: list[str] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        detail_lines.append(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    root = data_dir()
    missing = [s for s in SYMBOLS if not (root / f"{s}_1d.csv").exists()]
    check("data files present", not missing,
          f"{len(SYMBOLS) - len(missing)}/{len(SYMBOLS)} files in {root}"
          + (f" (missing: {', '.join(missing)})" if missing else ""))
    if missing:
        return {"gate": GATE_ID, "ok": False, "checks": checks,
                "detail": "\n".join(detail_lines)}

    try:
        signals, context = build_signals()
    except Exception as exc:  # noqa: BLE001 — gate reports any failure
        check("factor chain", False, f"{type(exc).__name__}: {exc}")
        return {"gate": GATE_ID, "ok": False, "checks": checks,
                "detail": "\n".join(detail_lines)}

    assets = context["assets"]
    check("data volume",
          all(a["bars"] >= MIN_BARS for a in assets.values()),
          ", ".join(f"{s}={a['bars']}" for s, a in assets.items()))
    check("factor computable",
          all(a["coverage"] >= MIN_COVERAGE for a in assets.values()),
          ", ".join(f"{s}={a['coverage']:.0%}" for s, a in assets.items()))
    check("orientation learned",
          all(a["orientation"] != 0.0 for a in assets.values()),
          ", ".join(f"{s}: train_ic={a['train_ic']:+.4f}"
                    if a["train_ic"] is not None else f"{s}: train_ic=N/A"
                    for s, a in assets.items()))
    check("positions non-flat",
          all(a["non_flat_frac"] > 0.0 for a in assets.values()),
          ", ".join(f"{s}={a['non_flat_frac']:.0%}"
                    for s, a in assets.items()))

    # ---- paper trading session on the factor signals ------------------ #
    from apps.runtime.paper_trading import (
        PaperAccount,
        PaperTradingSession,
        SignalSpec,
        SimulatedMarketFeed,
    )

    base_prices = {s: a["last_close"] or 100.0
                   for s, a in assets.items() if a.get("last_close")}
    feed = SimulatedMarketFeed(base_prices=base_prices, seed=42)
    session = PaperTradingSession(feed=feed,
                                  account=PaperAccount(initial_cash=1_000_000.0))
    specs = [SignalSpec(symbol=s, side=side, quantity=q, ref_price=ref)
             for (s, side, q, ref, _d) in signals]
    try:
        report = session.run(specs)
    except Exception as exc:  # noqa: BLE001
        check("paper session", False, f"{type(exc).__name__}: {exc}")
        return {"gate": GATE_ID, "ok": False, "checks": checks,
                "detail": "\n".join(detail_lines)}

    m = report["metrics"]
    check("signals generated", context["signals_total"] >= MIN_SIGNALS,
          f"{context['signals_total']} position changes "
          f"(min {MIN_SIGNALS})")
    check("paper execution healthy",
          m["signals"] > 0 and m["fill_rate_pct"] > 0
          and m["error_rate_pct"] < 50.0,
          f"fill={m['fill_rate_pct']}% reject={m['reject_rate_pct']}% "
          f"error={m['error_rate_pct']}%")
    check("account solvency", report["equity"] > 0,
          f"equity ${report['equity']:,.2f}, "
          f"ledger events {report['ledger_events']}")

    ok = all(c["ok"] for c in checks)
    detail_lines.insert(
        0,
        f"Factor {ALPHA_ID} on {'/'.join(SYMBOLS)} daily: "
        f"{'PASS' if ok else 'FAIL'}",
    )
    return {
        "gate": GATE_ID,
        "ok": ok,
        "checks": checks,
        "factor": {
            "alpha_id": ALPHA_ID,
            "assets": context["assets"],
            "signals_total": context["signals_total"],
            "windows": {"z_window": FACTOR_SPEC_REAL_D1.z_window,
                        "rank_window": FACTOR_SPEC_REAL_D1.rank_window},
            "note": ("long-only paper mapping: +1 -> 100 shares, else flat; "
                     "orientation is a train-only decision"),
        },
        "paper": report,
        "detail": "\n".join(detail_lines),
    }


def default_export_dir() -> Path:
    """Default paper-log export directory (research discovery output)."""
    return (Path(__file__).resolve().parents[2]
            / "research" / "discovery" / "output" / "factor-paper-d1")


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m apps.runtime factor",
        description="Alpha021 factor -> paper trading gate; "
                    "--export dumps the full trade/equity log as CSV.")
    parser.add_argument("--json", action="store_true",
                        help="output raw JSON")
    parser.add_argument("--export", nargs="?", const=str(default_export_dir()),
                        default=None, metavar="DIR",
                        help="export trades.csv / equity_curve.csv / "
                             "summary.csv (default dir: research/discovery/"
                             "output/factor-paper-d1)")
    args = parser.parse_args(argv if argv is not None else None)

    result = run_factor_gate()

    if args.export is not None:
        result["export"] = export_paper_log(Path(args.export))

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["ok"] else 1

    print(f"\n{GATE_TITLE}")
    print(result["detail"])
    if "export" in result:
        e = result["export"]
        print(f"\nExport: {e['out_dir']}")
        print(f"  trades.csv        — {e['signals']} signals, "
              f"realized PnL ${e['realized_pnl']:,.2f}")
        print(f"  equity_curve.csv  — daily mark-to-real-close equity, "
              f"final ${e['equity_final']:,.2f}")
        print("  summary.csv       — per-symbol fills / rejects / PnL")
    print(f"\nSummary: {'ALL CHECKS PASSED' if result['ok'] else 'CHECKS FAILED'}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
