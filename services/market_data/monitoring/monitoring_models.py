"""Market Data Monitoring domain vocabulary (Commit 013).

Commit 006 answers a *data-level* question — "may THIS quote be traded?"
Commit 013 answers a *system-level* question — "how is the whole market
data pipeline running?".  The two must never collapse into one module
(§2):: the Quality Gate is a per-event gate, Monitoring is an aggregate
observer that only records and displays — it never fixes data (§13).

Overall health (§17)::

    HEALTHY   adapter up, cache up, no serious quality problems
    DEGRADED  some symbols stale / cache abnormal / latency high
    BLOCKED   data cannot safely support trading (invalid / quarantined)
    OFFLINE   adapter / market data completely unavailable

Alert severities (§21): ``INFO`` < ``WARNING`` < ``CRITICAL``.

Alert types (§19) — the first version ships exactly the six the spec
lists, plus ``MARKET_DATA_RECOVERED`` which closes an incident (§22)::

    MARKET_DATA_OFFLINE / MARKET_DATA_STALE / MARKET_DATA_HIGH_LATENCY
    MARKET_DATA_GAP / REDIS_UNAVAILABLE / MARKET_DATA_INVALID

An ``INFO``-severity ``MarketDataIncident`` (§30) groups one alert type
from raise to recovery so the Dashboard can say::

    Last Incident
    Redis unavailable
    Duration: 42s
    Status: RECOVERED
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MarketDataHealth(str, Enum):
    """System-level market data health (§17)."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    OFFLINE = "OFFLINE"


class AlertSeverity(str, Enum):
    """Alert severity ladder (§21) — INFO < WARNING < CRITICAL."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertType(str, Enum):
    """First-version market data alerts (§19)."""

    MARKET_DATA_OFFLINE = "MARKET_DATA_OFFLINE"
    MARKET_DATA_STALE = "MARKET_DATA_STALE"
    MARKET_DATA_HIGH_LATENCY = "MARKET_DATA_HIGH_LATENCY"
    MARKET_DATA_GAP = "MARKET_DATA_GAP"
    REDIS_UNAVAILABLE = "REDIS_UNAVAILABLE"
    MARKET_DATA_INVALID = "MARKET_DATA_INVALID"
    MARKET_DATA_RECOVERED = "MARKET_DATA_RECOVERED"


class IncidentStatus(str, Enum):
    """Incident lifecycle (§30)."""

    OPEN = "OPEN"
    RECOVERED = "RECOVERED"


class AlertChange(str, Enum):
    """What happened to an alert on this evaluation (§20)."""

    RAISED = "RAISED"
    UPDATED = "UPDATED"
    RECOVERED = "RECOVERED"


#: Severity ranking — lets the engine compare without string table lookups.
_SEVERITY_RANK = {
    AlertSeverity.INFO.value: 0,
    AlertSeverity.WARNING.value: 1,
    AlertSeverity.CRITICAL.value: 2,
}


def severity_rank(severity: str) -> int:
    """Numeric rank of a severity (unknown → 0)."""
    return _SEVERITY_RANK.get(str(severity), 0)


@dataclass
class SymbolHealth:
    """One row of the Symbol Health table (§25).

    ``status`` is the Quality Gate verdict verbatim (``FRESH`` /
    ``WARNING`` / ``STALE`` / ``INVALID`` / ``QUARANTINED`` / ``OFFLINE``)
    so a symbol that the gate refuses can never read as healthy here.
    """

    symbol: str
    name: str = ""
    status: str = "OFFLINE"
    quote_age_ms: Optional[int] = None
    latency_ms: Optional[int] = None
    tradable: bool = False
    blocked_reason: Optional[str] = None
    bar_count: int = 0
    gaps: int = 0
    revisions: int = 0
    duplicates: int = 0
    last: Optional[str] = None

    @property
    def fresh(self) -> bool:
        return self.status == "FRESH"

    @property
    def stale(self) -> bool:
        return self.status in ("STALE", "INVALID", "QUARANTINED", "OFFLINE")

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "status": self.status,
            "quote_age_ms": self.quote_age_ms,
            "latency_ms": self.latency_ms,
            "tradable": self.tradable,
            "blocked_reason": self.blocked_reason,
            "bar_count": self.bar_count,
            "gaps": self.gaps,
            "revisions": self.revisions,
            "duplicates": self.duplicates,
            "last": self.last,
        }


@dataclass
class MarketDataAlert:
    """A deduplicated market data alert (§20).

    Repeated observations of the same condition update ``last_seen`` and
    bump ``count`` — they never append a new alert (§20: 100 stale
    detections must not produce 100 alerts).
    """

    alert_id: str
    type: str
    severity: str
    message: str
    symbol: Optional[str] = None
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    count: int = 1
    active: bool = True
    incident_id: Optional[str] = None

    @property
    def key(self) -> tuple:
        return (self.type, self.symbol)

    def as_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "type": self.type,
            "severity": self.severity,
            "message": self.message,
            "symbol": self.symbol,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "count": self.count,
            "active": self.active,
            "incident_id": self.incident_id,
        }


@dataclass
class MarketDataIncident:
    """An incident from raise to recovery (§22 / §30)."""

    incident_id: str
    type: str
    severity: str
    started_at: str
    status: str = IncidentStatus.OPEN.value
    symbol: Optional[str] = None
    recovered_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "incident_id": self.incident_id,
            "type": self.type,
            "severity": self.severity,
            "symbol": self.symbol,
            "started_at": self.started_at,
            "recovered_at": self.recovered_at,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "reason": self.reason,
        }


__all__ = [
    "MarketDataHealth",
    "AlertSeverity",
    "AlertType",
    "IncidentStatus",
    "AlertChange",
    "SymbolHealth",
    "MarketDataAlert",
    "MarketDataIncident",
    "severity_rank",
]
