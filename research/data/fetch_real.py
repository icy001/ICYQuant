"""Fetch real daily OHLCV data for the 9-asset research universe.

Free data sources (akshare), all retrievable from mainland China:

| Asset      | Source                                      | Notes                     |
|------------|---------------------------------------------|---------------------------|
| NVDA/SPY/  | ak.stock_us_hist(..., adjust='qfq')         | EastMoney, adjusted for   |
| QQQ        |                                             | splits (NVDA 2024 10:1)   |
| 000688.SH  | ak.stock_zh_index_daily('sh000688')         | Sina STAR-50 index        |
| HSTECH     | ak.stock_hk_index_daily_sina('HSTECH')      | Sina HSTECH index         |
| EURUSD     | ak.currency_boc_sina: EUR/CNY / USD/CNY     | cross rate, pseudo-OHLC   |
|            |                                             | (single price, volume=1) |
| XAUUSD     | ak.futures_foreign_hist('GC')               | COMEX gold proxy          |
| AU / AG    | ak.futures_main_sina('AU0'/'AG0')           | Sina dominant-continuous, |
|            |                                             | NOT roll-adjusted (known  |
|            |                                             | limitation, see manifest) |

Known limitations (recorded in the manifest, never silently "fixed"):
- AU/AG are dominant-continuous futures: contract rolls (~4-6x/year) create
  artificial gaps.  No reliable detector separates rolls from real holiday
  gaps, so no bar is removed — the fail-closed Factor Gate penalises any
  factor polluted by them.
- EURUSD has no volume: volume is filled with 1.0 so dollar-volume
  operators stay computable (they degenerate to constants, harmless).
- XAUUSD is proxied by COMEX gold front futures (daily corr with spot
  ~0.999).

Output: ``data/real/d1/{SYMBOL}_1d.csv`` in the same schema as
``data/processed`` (timestamp, open, high, low, close, volume) plus a
``manifest.json`` describing provenance.

Usage:
    python -m research.data.fetch_real --start 2024-01-01 --end 2026-08-19
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd

OUTPUT_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def _clip_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """Enforce high >= max(o, c) and low <= min(o, c) (dirty-tick repair)."""
    df = df.copy()
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"] = df[["low", "open", "close"]].min(axis=1)
    return df


def _fetch_us_stock(symbol_em: str) -> pd.DataFrame:
    """EastMoney qfq daily bars, with a Sina fallback + split repair.

    The fallback detects stock splits (e.g. NVDA 2024-06-10 10:1) as
    |close-to-close| jumps > 50% whose inverse is near an integer, and
    rescales all earlier prices by 1/split (forward adjustment).
    """
    import akshare as ak
    df = None
    for attempt in range(3):
        try:
            df = ak.stock_us_hist(symbol=symbol_em, period="daily",
                                  start_date="20200101", end_date="20261231",
                                  adjust="qfq")
            break
        except Exception:
            time.sleep(5.0 * (attempt + 1))
    if df is None or df.empty:
        # Sina fallback (unadjusted raw bars, qfq endpoint is unreliable):
        # fetch https://finance.sina.com.cn/staticdata/us/{sym} and decode
        # with akshare's own JS decoder, then repair splits ourselves.
        import requests
        from py_mini_racer import MiniRacer
        from akshare.stock.stock_us_sina import zh_js_decode
        sina_symbol = symbol_em.split(".", 1)[1].lower()
        res = requests.get(
            f"https://finance.sina.com.cn/staticdata/us/{sina_symbol}",
            timeout=20)
        js = MiniRacer()
        js.eval(zh_js_decode)
        payload = js.call(
            "d", res.text.split("=")[1].split(";")[0].replace('"', ""))
        raw = pd.DataFrame(payload).sort_values("date").reset_index(drop=True)
        raw["date"] = pd.to_datetime(raw["date"], utc=True).dt.tz_localize(None)
        for col in ("open", "high", "low", "close", "volume"):
            raw[col] = raw[col].astype(float)
        raw = raw.sort_values("date").reset_index(drop=True)
        splits: list[tuple[str, float]] = []
        for i in range(1, len(raw)):
            prev_c, cur_c = raw["close"].iloc[i - 1], raw["close"].iloc[i]
            if prev_c > 0 and cur_c > 0:
                ratio = prev_c / cur_c
                if ratio > 1.5:
                    n = round(ratio)
                    if n >= 2 and abs(ratio - n) / n < 0.05:
                        d = raw["date"].iloc[i]
                        splits.append((str(d)[:10], float(n)))
                        # forward-adjust all bars before the split
                        raw.loc[: i - 1, ["open", "high", "low", "close"]] \
                            = raw.loc[: i - 1, ["open", "high", "low", "close"]] / n
        print(f"[fetch]   sina fallback for {sina_symbol.upper()}, "
              f"split repairs: {splits or 'none'}")
        return pd.DataFrame({
            "date": pd.to_datetime(raw["date"]),
            "open": raw["open"].astype(float),
            "high": raw["high"].astype(float),
            "low": raw["low"].astype(float),
            "close": raw["close"].astype(float),
            "volume": raw["volume"].astype(float),
        })
    return pd.DataFrame({
        "date": pd.to_datetime(df["日期"]),
        "open": df["开盘"].astype(float),
        "high": df["最高"].astype(float),
        "low": df["最低"].astype(float),
        "close": df["收盘"].astype(float),
        "volume": df["成交量"].astype(float),
    })


def _fetch_index_sina(symbol: str) -> pd.DataFrame:
    import akshare as ak
    df = ak.stock_zh_index_daily(symbol=symbol)
    return pd.DataFrame({
        "date": pd.to_datetime(df["date"]),
        "open": df["open"].astype(float),
        "high": df["high"].astype(float),
        "low": df["low"].astype(float),
        "close": df["close"].astype(float),
        "volume": df["volume"].astype(float),
    })


def _fetch_hstech() -> pd.DataFrame:
    import akshare as ak
    df = ak.stock_hk_index_daily_sina(symbol="HSTECH")
    return pd.DataFrame({
        "date": pd.to_datetime(df["date"]),
        "open": df["open"].astype(float),
        "high": df["high"].astype(float),
        "low": df["low"].astype(float),
        "close": df["close"].astype(float),
        "volume": df["volume"].astype(float),
    })


def _fetch_eurusd_cross() -> pd.DataFrame:
    """EURUSD = BOC EUR/CNY quote / BOC USD/CNY quote (same source & day)."""
    import akshare as ak
    eur = ak.currency_boc_sina(symbol="欧元", start_date="20200101",
                               end_date="20261231")
    usd = ak.currency_boc_sina(symbol="美元", start_date="20200101",
                               end_date="20261231")
    eur = eur[["日期", "中行折算价"]].rename(
        columns={"日期": "date", "中行折算价": "eur"})
    usd = usd[["日期", "中行折算价"]].rename(
        columns={"日期": "date", "中行折算价": "usd"})
    df = eur.merge(usd, on="date", how="inner")
    df["date"] = pd.to_datetime(df["date"])
    df["rate"] = df["eur"].astype(float) / df["usd"].astype(float)
    # pseudo-OHLC: single daily reference price, volume filled with 1.0
    return pd.DataFrame({
        "date": df["date"],
        "open": df["rate"], "high": df["rate"],
        "low": df["rate"], "close": df["rate"],
        "volume": 1.0,
    })


def _fetch_gc() -> pd.DataFrame:
    import akshare as ak
    df = ak.futures_foreign_hist(symbol="GC")
    return pd.DataFrame({
        "date": pd.to_datetime(df["date"]),
        "open": df["open"].astype(float),
        "high": df["high"].astype(float),
        "low": df["low"].astype(float),
        "close": df["close"].astype(float),
        "volume": df["volume"].astype(float),
    })


def _fetch_cn_futures(symbol: str) -> pd.DataFrame:
    import akshare as ak
    df = ak.futures_main_sina(symbol=symbol, start_date="20200101",
                              end_date="20261231")
    return pd.DataFrame({
        "date": pd.to_datetime(df["日期"]),
        "open": df["开盘价"].astype(float),
        "high": df["最高价"].astype(float),
        "low": df["最低价"].astype(float),
        "close": df["收盘价"].astype(float),
        "volume": df["成交量"].astype(float),
    })


# asset -> (fetcher, source description, limitation)
FETCHERS: dict[str, tuple[Callable[[], pd.DataFrame], str, str]] = {
    "NVDA": (lambda: _fetch_us_stock("105.NVDA"),
             "EastMoney US daily, qfq (split-adjusted)", ""),
    "SPY": (lambda: _fetch_us_stock("106.SPY"),
            "EastMoney US daily, qfq", ""),
    "QQQ": (lambda: _fetch_us_stock("105.QQQ"),
            "EastMoney US daily, qfq", ""),
    "000688.SH": (lambda: _fetch_index_sina("sh000688"),
                  "Sina STAR-50 index daily", ""),
    "HSTECH": (_fetch_hstech, "Sina HSTECH index daily", ""),
    "EURUSD": (_fetch_eurusd_cross,
               "BOC cross rate: EUR/CNY / USD/CNY (中行折算价)",
               "pseudo-OHLC (single daily price), volume=1.0"),
    "XAUUSD": (_fetch_gc, "COMEX gold front futures (GC) daily",
               "spot XAUUSD proxied by GC futures"),
    "AU": (lambda: _fetch_cn_futures("AU0"),
           "Sina SHFE gold dominant-continuous (AU0) daily",
           "not roll-adjusted: contract rolls create artificial gaps"),
    "AG": (lambda: _fetch_cn_futures("AG0"),
           "Sina SHFE silver dominant-continuous (AG0) daily",
           "not roll-adjusted: contract rolls create artificial gaps"),
}


def fetch_one(asset: str, start: date, end: date) -> pd.DataFrame:
    fetcher, _, _ = FETCHERS[asset]
    df = fetcher()
    df = _clip_ohlc(df)
    df = df[(df["date"] >= pd.Timestamp(start))
            & (df["date"] <= pd.Timestamp(end))]
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def save_csv(df: pd.DataFrame, path: Path) -> None:
    out = pd.DataFrame({
        "timestamp": df["date"].dt.strftime("%Y-%m-%dT00:00:00"),
        "open": df["open"].round(6),
        "high": df["high"].round(6),
        "low": df["low"].round(6),
        "close": df["close"].round(6),
        "volume": df["volume"].round(2),
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m research.data.fetch_real",
        description="Fetch real daily data for the 9-asset research universe.")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2026-08-19")
    parser.add_argument("--out", type=Path,
                        default=Path(__file__).resolve().parents[2]
                        / "data" / "real" / "d1")
    parser.add_argument("--assets", nargs="+", default=None,
                        help="Subset of assets (default: all 9).")
    args = parser.parse_args(argv)

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    assets = args.assets or list(FETCHERS)

    manifest: dict[str, Any] = {
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "range": [start.isoformat(), end.isoformat()],
        "assets": {},
    }
    failures: list[str] = []
    for asset in assets:
        _, source, limitation = FETCHERS[asset]
        try:
            df = fetch_one(asset, start, end)
            save_csv(df, args.out / f"{asset}_1d.csv")
            manifest["assets"][asset] = {
                "source": source,
                "rows": len(df),
                "first": df["date"].iloc[0].date().isoformat(),
                "last": df["date"].iloc[-1].date().isoformat(),
                "limitation": limitation,
            }
            print(f"[fetch] {asset:10s} {len(df):5d} bars "
                  f"{manifest['assets'][asset]['first']} -> "
                  f"{manifest['assets'][asset]['last']}")
        except Exception as exc:
            failures.append(asset)
            print(f"[fetch] {asset:10s} FAIL {type(exc).__name__}: "
                  f"{str(exc)[:80]}")
        time.sleep(1.0)  # be polite to the free endpoints

    (args.out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[fetch] manifest: {args.out / 'manifest.json'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
