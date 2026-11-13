# -*- coding: utf-8 -*-
"""Shadow-trading runner for the M5 reversal revival validation.

Purpose: measure the REAL all-in execution cost of the canonical
H12_down strategy before any automated execution is built. The runner
never places orders; it emits signals and records theoretical fills so
they can be compared against your manual MT5 fills.

Pipeline
--------
MT5 (M1_Exporter.mq5) --CSV--> this runner:
    1. tail M1 bars, convert server time -> Beijing
    2. resample to M5 (identical construction to research load_m5)
    3. feed the bit-exact M5ReversalSignal (calendar-gated)
    4. on signal: entry = next bar open, exit = close 12 bars later
    5. log everything to shadow_log.csv; runtime gap detection flags
       feed outages inside open trades (operational anomaly layer)

Usage
-----
    python -m research.live.shadow_runner \
        --csv "<MT5 Files>/ICYQuant/EURUSD_M1_live.csv" \
        --server-offset-hours 2 \
        --log artifacts/live_shadow/shadow_log.csv

Server offset: MT5 server time minus UTC (usually +2 or +3). Verify on
the first bar: logged server time vs your wall clock UTC.
"""
from __future__ import annotations

import argparse
import csv
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from research.live.fx_calendar import can_hold, is_fx_closed
from research.live.m5_reversal_signal import M5ReversalSignal, Bar

PIP = 1e-4
COST_PIPS = 0.15            # negotiated terms; mirrors costs.py
EXPECTED_NET_PIPS = 0.1828  # revival verdict, full-sample
M1_STALE_SECONDS = 7 * 60   # no M1 bar for 7 min in market hours = anomaly


@dataclass
class OpenTrade:
    signal_ts: datetime
    entry_ts: datetime
    entry_px: float
    exit_bar_ts: datetime
    flagged: bool = False


class ShadowRunner:
    def __init__(self, csv_path: str, log_path: str, server_offset_hours: int):
        self.csv_path = Path(csv_path)
        self.log_path = Path(log_path)
        self.offset = timedelta(hours=server_offset_hours + 8)  # server->Beijing
        self.gen = M5ReversalSignal(can_hold=can_hold)
        self.open_trade: OpenTrade | None = None
        self._pending_signal = None
        self.closed: list[dict] = []
        self._m1_buffer: dict[datetime, dict] = {}
        self._last_m5_ts: datetime | None = None
        self._last_m1_seen: datetime | None = None
        self._pos = 0
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            with self.log_path.open("w", newline="") as f:
                csv.writer(f).writerow(
                    ["event", "ts_beijing", "detail"])

    # ------------------------------------------------------------------
    def _log(self, event: str, ts: datetime, detail: str) -> None:
        with self.log_path.open("a", newline="") as f:
            csv.writer(f).writerow([event, ts.isoformat(), detail])
        print(f"[{ts:%Y-%m-%d %H:%M}] {event}: {detail}", flush=True)

    # ------------------------------------------------------------------
    def _read_new_m1(self) -> list[dict]:
        if not self.csv_path.exists():
            return []
        size = self.csv_path.stat().st_size
        if size < self._pos:                    # file rotated/truncated
            self._pos = 0
        rows = []
        with self.csv_path.open() as f:
            f.seek(self._pos)
            reader = csv.reader(f)
            for row in reader:
                if not row or row[0] == "server_time":
                    continue
                try:
                    ts = datetime.strptime(row[0], "%Y.%m.%d %H:%M")
                except ValueError:
                    continue
                rows.append({"ts_server": ts,
                             "open": float(row[1]), "high": float(row[2]),
                             "low": float(row[3]), "close": float(row[4])})
            self._pos = f.tell()
        return rows

    # ------------------------------------------------------------------
    def _m5_bucket(self, ts_beijing: datetime) -> datetime:
        return ts_beijing.replace(minute=ts_beijing.minute // 5 * 5,
                                  second=0, microsecond=0)

    def _feed_m1(self, row: dict) -> None:
        ts_bj = row["ts_server"] + self.offset
        self._last_m1_seen = datetime.utcnow()
        bucket = self._m5_bucket(ts_bj)
        b = self._m1_buffer.get(bucket)
        if b is None:
            # starting a new M5 bucket: close the previous one if complete
            self._close_completed_buckets(before=bucket)
            self._m1_buffer[bucket] = {
                "open": row["open"], "high": row["high"],
                "low": row["low"], "close": row["close"]}
        else:
            b["high"] = max(b["high"], row["high"])
            b["low"] = min(b["low"], row["low"])
            b["close"] = row["close"]

    def _close_completed_buckets(self, before: datetime) -> None:
        for ts in sorted(t for t in self._m1_buffer if t < before):
            # only close a bucket that had all five M1 minutes
            b = self._m1_buffer.pop(ts)
            if ts + timedelta(minutes=5) <= before:
                self._on_m5(Bar(ts=ts, open=b["open"], high=b["high"],
                                low=b["low"], close=b["close"]))

    # ------------------------------------------------------------------
    def _on_m5(self, bar: Bar) -> None:
        self._last_m5_ts = bar.ts

        # 1) entry fill: open of the bar after the signal bar
        if self.open_trade is None and self._pending_signal is not None:
            sig = self._pending_signal
            self._pending_signal = None
            if bar.ts == sig.signal_bar_ts + timedelta(minutes=5):
                self.open_trade = OpenTrade(
                    signal_ts=sig.signal_bar_ts, entry_ts=bar.ts,
                    entry_px=bar.open,
                    exit_bar_ts=bar.ts + timedelta(minutes=55))
                self._log("ENTRY", bar.ts,
                          f"LONG @ {bar.open:.5f} (signal {sig.reason})")

        # 2) exit fill: close of the 12th bar after entry
        if self.open_trade is not None and bar.ts >= self.open_trade.exit_bar_ts:
            t = self.open_trade
            self.open_trade = None
            gross = (bar.close - t.entry_px) / PIP
            net = gross - COST_PIPS
            flag = " FLAGGED(feed-gap)" if t.flagged else ""
            self.closed.append({"entry": t.entry_ts, "exit": bar.ts,
                                "gross": gross, "net": net})
            self._log("EXIT", bar.ts,
                      f"@ {bar.close:.5f}  gross {gross:+.2f}  "
                      f"net {net:+.2f} pip{flag}")
            self._print_stats()

        # 3) new signal (only when flat — nonoverlap makes nested impossible)
        if self.open_trade is None:
            sig = self.gen.update(bar)
            if sig is not None:
                self._pending_signal = sig
                self._log("SIGNAL", bar.ts, sig.reason)

    # ------------------------------------------------------------------
    def _print_stats(self) -> None:
        n = len(self.closed)
        if n == 0:
            return
        nets = [t["net"] for t in self.closed]
        mean = sum(nets) / n
        wins = sum(1 for x in nets if x > 0)
        self._log("STATS", datetime.now(),
                  f"trades={n} win={wins / n:.0%} "
                  f"mean_net={mean:+.4f} pip (expect {EXPECTED_NET_PIPS:+.4f})")

    def check_feed_health(self) -> None:
        """Runtime gap layer: feed outage during an open trade = flag."""
        if self._last_m1_seen is None:
            return
        silent = (datetime.utcnow() - self._last_m1_seen).total_seconds()
        if silent > M1_STALE_SECONDS:
            now_bj = datetime.utcnow() + timedelta(hours=8)
            if not is_fx_closed(now_bj):
                if self.open_trade is not None and not self.open_trade.flagged:
                    self.open_trade.flagged = True
                    self._log("ANOMALY", now_bj,
                              f"feed silent {silent:.0f}s with open trade — "
                              f"exit price unreliable, manage manually")

    # ------------------------------------------------------------------
    def run(self) -> None:
        self._log("START", datetime.now(),
                  f"tailing {self.csv_path} (offset server+{self.offset})")
        while True:
            try:
                for row in self._read_new_m1():
                    self._feed_m1(row)
                self.check_feed_health()
                time.sleep(2)
            except KeyboardInterrupt:
                self._log("STOP", datetime.now(),
                          f"closed_trades={len(self.closed)}")
                return


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv", required=True, help="MT5 exporter CSV path")
    ap.add_argument("--log", default="artifacts/live_shadow/shadow_log.csv")
    ap.add_argument("--server-offset-hours", type=int, default=2,
                    help="MT5 server time minus UTC (usually 2 or 3)")
    args = ap.parse_args()
    ShadowRunner(args.csv, args.log, args.server_offset_hours).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
