"""Dataset Manifest — the research dataset registry.

Each dataset file (``{symbol}_{timeframe}.csv``) is described by a
``DatasetManifest`` record so that Raw -> Processed -> Manifest -> Quality
Gate -> Backtest is fully traceable. Manifests are stored as JSON under
``data/manifests/``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .types import TimeFrame
from ..universe.asset import Asset, TradingSession


@dataclass(frozen=True)
class QualityGateResult:
    status: str = ""  # PASS | FAIL
    checks: dict[str, bool] = field(default_factory=dict)
    detail: dict[str, Any] = field(default_factory=dict)
    run_at: str = ""


@dataclass(frozen=True)
class DatasetManifest:
    symbol: str
    timeframe: str  # TimeFrame value, e.g. "15m"
    source: str = "synthetic"
    timezone: str = "UTC"
    session: Optional[str] = None  # human-readable trading session
    continuous_contract: bool = False
    start: str = ""
    end: str = ""
    bars: int = 0
    min_years: float = 0.0
    quality_gate: QualityGateResult = field(default_factory=QualityGateResult)
    generated_at: str = ""

    # --- construction -----------------------------------------------------

    @classmethod
    def build(
        cls,
        asset: Asset,
        timeframe: TimeFrame,
        bars: list,
        min_years: float = 3.0,
        source: str = "synthetic",
    ) -> "DatasetManifest":
        """Build a manifest from an asset, timeframe and loaded bars."""
        if not bars:
            start = end = ""
        else:
            start = bars[0].timestamp.isoformat() if hasattr(bars[0], "timestamp") else ""
            end = bars[-1].timestamp.isoformat() if hasattr(bars[-1], "timestamp") else ""
        return cls(
            symbol=asset.symbol,
            timeframe=timeframe.value,
            source=source,
            timezone=asset.timezone,
            session=str(asset.session) if asset.session else None,
            continuous_contract=asset.continuous_contract,
            start=start,
            end=end,
            bars=len(bars),
            min_years=min_years,
            generated_at=datetime.now().isoformat(timespec="seconds"),
        )

    # --- (de)serialization -------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DatasetManifest":
        qg = data.get("quality_gate") or {}
        return cls(
            symbol=data["symbol"],
            timeframe=data["timeframe"],
            source=data.get("source", "synthetic"),
            timezone=data.get("timezone", "UTC"),
            session=data.get("session"),
            continuous_contract=data.get("continuous_contract", False),
            start=data.get("start", ""),
            end=data.get("end", ""),
            bars=int(data.get("bars", 0)),
            min_years=float(data.get("min_years", 0.0)),
            quality_gate=QualityGateResult(
                status=qg.get("status", ""),
                checks=qg.get("checks", {}),
                detail=qg.get("detail", {}),
                run_at=qg.get("run_at", ""),
            ),
            generated_at=data.get("generated_at", ""),
        )

    @classmethod
    def from_json(cls, text: str) -> "DatasetManifest":
        return cls.from_dict(json.loads(text))


def manifest_path(data_root: Path, symbol: str, timeframe: str) -> Path:
    """Conventional manifest path: ``data/manifests/{symbol}_{tf}.json``."""
    return data_root / "manifests" / f"{symbol}_{timeframe}.json"


def write_manifest(manifest: DatasetManifest, data_root: Path) -> Path:
    """Persist a manifest under ``data/manifests/`` and return its path."""
    path = manifest_path(data_root, manifest.symbol, manifest.timeframe)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.to_json(), encoding="utf-8")
    return path


def load_manifest(path: Path) -> DatasetManifest:
    return DatasetManifest.from_json(path.read_text(encoding="utf-8"))


def _session_repr(session: Optional[TradingSession]) -> Optional[str]:
    if session is None:
        return None
    return str(session)
