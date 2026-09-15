"""Monitoring configuration — env driven (Commit 013).

Freshness thresholds are **not** re-invented here: the monitor reads the
same ``QualityConfig`` (Commit 006) thresholds the write-path gate uses,
so Monitoring and the Quality Gate can never disagree about what
``STALE`` means.  Only the monitoring-only knobs (latency warning,
history sizes, throughput window) live here::

    MARKET_MONITOR_ENABLED            bool   master switch   (default true)
    MARKET_MONITOR_LATENCY_WARN_MS    int    §21 WARNING     (default 200)
    MARKET_MONITOR_LATENCY_CRIT_MS    int    §21 CRITICAL    (default 1000)
    MARKET_MONITOR_GAP_ALERT          bool   raise gap alert (default true)
    MARKET_MONITOR_ALERT_HISTORY      int    alert ring size (default 200)
    MARKET_MONITOR_INCIDENT_HISTORY   int    incident ring  (default 100)
    MARKET_MONITOR_THROUGHPUT_WINDOW  float  rate window s  (default 30.0)
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on", "y")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class MonitoringConfig:
    """Thresholds and ring sizes for the monitoring observer (§21-§22)."""

    enabled: bool = True
    latency_warn_ms: int = 200
    latency_critical_ms: int = 1000
    gap_alert: bool = True
    alert_history: int = 200
    incident_history: int = 100
    throughput_window_s: float = 30.0

    @classmethod
    def from_env(cls) -> "MonitoringConfig":
        return cls(
            enabled=_env_bool("MARKET_MONITOR_ENABLED", True),
            latency_warn_ms=_env_int("MARKET_MONITOR_LATENCY_WARN_MS", 200),
            latency_critical_ms=_env_int(
                "MARKET_MONITOR_LATENCY_CRIT_MS", 1000
            ),
            gap_alert=_env_bool("MARKET_MONITOR_GAP_ALERT", True),
            alert_history=_env_int("MARKET_MONITOR_ALERT_HISTORY", 200),
            incident_history=_env_int("MARKET_MONITOR_INCIDENT_HISTORY", 100),
            throughput_window_s=_env_float(
                "MARKET_MONITOR_THROUGHPUT_WINDOW", 30.0
            ),
        )

    def freshness(self) -> dict:
        """Freshness thresholds, single-sourced from the Quality Gate."""
        try:
            from ..quality.quality_config import QualityConfig

            cfg = QualityConfig.from_env()
            return {
                "fresh_ms": int(getattr(cfg, "fresh_ms", 3000)),
                "warning_ms": int(getattr(cfg, "warning_ms", 10000)),
                "stale_ms": int(getattr(cfg, "stale_ms", 10000)),
            }
        except Exception:  # noqa: BLE001 — fall back to documented defaults
            return {"fresh_ms": 3000, "warning_ms": 10000, "stale_ms": 10000}

    def as_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "latency_warn_ms": self.latency_warn_ms,
            "latency_critical_ms": self.latency_critical_ms,
            "gap_alert": self.gap_alert,
            "alert_history": self.alert_history,
            "incident_history": self.incident_history,
            "throughput_window_s": self.throughput_window_s,
            "freshness": self.freshness(),
        }


__all__ = ["MonitoringConfig"]
