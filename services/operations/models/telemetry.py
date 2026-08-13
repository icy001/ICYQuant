"""Telemetry context model (Commit 27 Part 1.2, spec sections 12-13).

一个 Metric 不只是 "latency = 20ms"，还知道：

    service    = risk-engine
    instance   = risk-02
    environment= production
    version    = 0.4.0-alpha2
    trace_id   = 8f31...

trace_id 让运营人员把 Metric / Log / Event / Order / Incident 串起来，
这是后续 Incident Investigation 的基础（spec section 13）：

    Trace -> Risk latency / Admission latency / Execution latency / Venue latency / Fill
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TelemetryContext:

    timestamp: datetime

    service_id: str

    instance_id: str

    environment: str

    version: str

    trace_id: str | None = None

    request_id: str | None = None
