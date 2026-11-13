# -*- coding: utf-8 -*-
"""Shadow-runner 的行情源适配层。

两个源，输出统一的 M1 bar 流（UTC 时间戳）：

* CsvFeed   — MT5 M1_Exporter.mq5 导出的 CSV（首选：与执行券商同价）
* OandaFeed — OANDA 免费模拟账户 REST API（免编译备用：Mac 直读；
              与执行券商有零点差级报价差，成本复核时单独核对）

OANDA 需要一个免费 practice 账户（oanda.com 注册即得 API token），
价格与真实 MT5 券商不完全一致——这没关系：影子期验证的是"信号逻辑 +
真实成交成本"，信号源的微小价差在复核时会通过成交价对比显形。
"""
from __future__ import annotations

import csv
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional


class CsvFeed:
    """Tails the MT5 exporter CSV. Yields completed M1 bars (server time)."""

    def __init__(self, path: str):
        self.path = Path(path)
        self._pos = 0

    def poll(self) -> list[dict]:
        if not self.path.exists():
            return []
        if self.path.stat().st_size < self._pos:   # rotated/truncated
            self._pos = 0
        out = []
        with self.path.open() as f:
            f.seek(self._pos)
            for row in csv.reader(f):
                if not row or row[0] == "server_time":
                    continue
                try:
                    ts = datetime.strptime(row[0], "%Y.%m.%d %H:%M")
                except ValueError:
                    continue
                out.append({"ts_server": ts, "open": float(row[1]),
                            "high": float(row[2]), "low": float(row[3]),
                            "close": float(row[4])})
            self._pos = f.tell()
        return out


class OandaFeed:
    """Polls OANDA practice REST for the latest completed M1 candle.

    Env vars: OANDA_TOKEN (required), OANDA_HOST (default practice host).
    """

    HOST = "https://api-fxpractice.oanda.com"

    def __init__(self, token: str, instrument: str = "EUR_USD",
                 host: Optional[str] = None):
        self.token = token
        self.instrument = instrument
        self.host = host or self.HOST
        self._last_candle_start: Optional[str] = None

    def poll(self) -> list[dict]:
        url = (f"{self.host}/v3/instruments/{self.instrument}/candles"
               f"?price=M&granularity=M1&count=3")
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {self.token}"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        out = []
        for c in data.get("candles", []):
            if not c.get("complete"):
                continue
            if c["time"] == self._last_candle_start:
                continue
            self._last_candle_start = c["time"]
            m = c["mid"]
            # OANDA time is RFC3339 UTC; shadow runner treats feed bars as
            # "server" time, so emit ts_server in UTC and set offset 0.
            ts = datetime.fromisoformat(c["time"].replace("Z", "+00:00")) \
                          .astimezone(timezone.utc).replace(tzinfo=None)
            out.append({"ts_server": ts, "open": float(m["o"]),
                        "high": float(m["h"]), "low": float(m["l"]),
                        "close": float(m["c"])})
        return out


def make_feed(name: str, **kw):
    if name == "csv":
        return CsvFeed(kw["csv_path"])
    if name == "oanda":
        return OandaFeed(kw["token"], kw.get("instrument", "EUR_USD"))
    raise ValueError(f"unknown feed: {name}")
