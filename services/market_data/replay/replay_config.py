"""Replay configuration (Commit 012 §6 / §12 / §16).

Commit 012 adds **no second market data system**.  The engine re-emits
the *existing* historical series (Commit 008) on a virtual clock, so one
window can be re-run by Paper (009), Shadow (016) and the test gates
with byte-identical results.  Replay is a *source*, never a database.

Everything is environment-driven, never hard-coded in business logic::

    MARKET_REPLAY_ENABLED            master switch                (true)
    MARKET_REPLAY_TIMEFRAME          only 1m in Phase 1           (1m)
    MARKET_REPLAY_DEFAULT_SPEED      §6 speed, 0 = manual step    (1.0)
    MARKET_REPLAY_SPEED_LIMIT        clamp for auto-start drivers (100.0)
    MARKET_REPLAY_DEFAULT_LIMIT      bars per symbol by default   (200)
    MARKET_REPLAY_MAX_LIMIT          hard cap per load()          (500)
    MARKET_REPLAY_MAX_SLEEP_S        clamp one paced sleep (§14)  (60.0)
    MARKET_REPLAY_ENFORCE_CALENDAR   quarantine non-trading bars  (true)
    MARKET_REPLAY_ENFORCE_QUALITY    run 006 Bar quality gate     (true)
    MARKET_REPLAY_ALLOW_UNKNOWN      accept unregistered symbols  (false)
    MARKET_REPLAY_STRICT_JUNCTION    refuse not-yet-knowable bars (true)

Speed (§6) is a whitelist, not a range: ``0`` (manual step), ``0.1``,
``1``, ``2``, ``10``, ``50``, ``100``.  ``0`` is the §7 debug mode —
nothing advances until the operator calls ``step()``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from .replay_clock import ReplayClock

_TRUE_TOKENS = {"1", "true", "yes", "on", "y"}
_FALSE_TOKENS = {"0", "false", "no", "off", "n"}

# Wall-clock seconds one frame occupies at x1 speed (used only for
# documentation / status; pacing itself divides the virtual delta).
_FRAME_SECONDS: dict[str, float] = {
    "1m": 60.0,
    "5m": 300.0,
    "15m": 900.0,
    "30m": 1800.0,
    "1h": 3600.0,
    "1d": 86400.0,
}

# §11 — Phase 1 replays 1m only.  The tuple exists so a future commit can
# widen it without touching call sites.
SUPPORTED_TIMEFRAMES: tuple[str, ...] = ("1m",)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    token = raw.strip().lower()
    if token in _TRUE_TOKENS:
        return True
    if token in _FALSE_TOKENS:
        return False
    return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


def _coerce_speed(value: float, default: float) -> float:
    """Snap a speed onto the §6 whitelist, falling back to ``default``."""
    try:
        speed = float(value)
    except (TypeError, ValueError):
        return default
    return speed if speed in ReplayClock.ALLOWED_SPEEDS else default


@dataclass(frozen=True)
class ReplayConfig:
    """Resolved replay settings (env keys documented in the module docstring)."""

    enabled: bool = True
    timeframe: str = "1m"
    default_speed: float = 1.0
    default_limit: int = 200
    max_limit: int = 500
    max_sleep_seconds: float = 60.0
    enforce_calendar: bool = True
    enforce_quality: bool = True
    allow_unknown: bool = False
    strict_junction: bool = True

    @classmethod
    def from_env(cls) -> "ReplayConfig":
        """Build from environment, falling back to safe defaults."""
        default_limit = max(1, _env_int("MARKET_REPLAY_DEFAULT_LIMIT", 200))
        max_limit = max(default_limit, _env_int("MARKET_REPLAY_MAX_LIMIT", 500))
        timeframe = _env_str("MARKET_REPLAY_TIMEFRAME", "1m")
        if timeframe not in SUPPORTED_TIMEFRAMES:
            timeframe = SUPPORTED_TIMEFRAMES[0]
        return cls(
            enabled=_env_bool("MARKET_REPLAY_ENABLED", True),
            timeframe=timeframe,
            default_speed=_coerce_speed(
                _env_float("MARKET_REPLAY_DEFAULT_SPEED", 1.0), 1.0
            ),
            default_limit=default_limit,
            max_limit=max_limit,
            max_sleep_seconds=max(
                0.0, _env_float("MARKET_REPLAY_MAX_SLEEP_S", 60.0)
            ),
            enforce_calendar=_env_bool("MARKET_REPLAY_ENFORCE_CALENDAR", True),
            enforce_quality=_env_bool("MARKET_REPLAY_ENFORCE_QUALITY", True),
            allow_unknown=_env_bool("MARKET_REPLAY_ALLOW_UNKNOWN", False),
            strict_junction=_env_bool("MARKET_REPLAY_STRICT_JUNCTION", True),
        )

    # ── derived ──────────────────────────────────────────────────

    def resolve_speed(self, speed: Optional[float] = None) -> float:
        """Validate a caller speed against §6, or keep the default."""
        if speed is None:
            return self.default_speed
        if float(speed) not in ReplayClock.ALLOWED_SPEEDS:
            return self.default_speed
        return float(speed)

    def resolve_limit(self, limit: Optional[int]) -> int:
        """Clamp a caller-supplied limit into ``[1, max_limit]``."""
        value = self.default_limit if limit is None else int(limit)
        return max(1, min(value, self.max_limit))

    @property
    def frame_seconds(self) -> float:
        """Wall-clock seconds one frame occupies at x1 speed."""
        return _FRAME_SECONDS.get(self.timeframe, 60.0)

    def as_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "timeframe": self.timeframe,
            "default_speed": self.default_speed,
            "allowed_speeds": list(ReplayClock.ALLOWED_SPEEDS),
            "default_limit": self.default_limit,
            "max_limit": self.max_limit,
            "max_sleep_seconds": self.max_sleep_seconds,
            "enforce_calendar": self.enforce_calendar,
            "enforce_quality": self.enforce_quality,
            "allow_unknown": self.allow_unknown,
            "strict_junction": self.strict_junction,
            "frame_seconds": self.frame_seconds,
        }


__all__ = ["ReplayConfig", "SUPPORTED_TIMEFRAMES"]
