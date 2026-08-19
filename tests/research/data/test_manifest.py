"""Tests for the DatasetManifest registry."""
from __future__ import annotations

from pathlib import Path

from research.data.bar import Bar
from research.data.manifest import (
    DatasetManifest,
    QualityGateResult,
    load_manifest,
    manifest_path,
    write_manifest,
)
from research.data.types import TimeFrame
from research.universe.research_universe import by_symbol


def _bars():
    from datetime import datetime
    return [
        Bar(symbol="AU", timestamp=datetime(2023, 1, 3, 9, 0),
            open=400.0, high=401.0, low=399.0, close=400.5, volume=100),
        Bar(symbol="AU", timestamp=datetime(2023, 1, 3, 9, 15),
            open=400.5, high=402.0, low=400.0, close=401.0, volume=120),
    ]


def test_build_manifest_fields():
    asset = by_symbol("AU")
    manifest = DatasetManifest.build(asset, TimeFrame.M15, _bars(), min_years=3.0)
    assert manifest.symbol == "AU"
    assert manifest.timeframe == "15m"
    assert manifest.timezone == "Asia/Shanghai"
    assert manifest.continuous_contract is True
    assert manifest.bars == 2
    assert manifest.start and manifest.end


def test_manifest_json_roundtrip():
    asset = by_symbol("AU")
    m1 = DatasetManifest.build(asset, TimeFrame.M15, _bars(), min_years=3.0)
    m1 = DatasetManifest(
        symbol=m1.symbol, timeframe=m1.timeframe, source=m1.source,
        timezone=m1.timezone, session=m1.session,
        continuous_contract=m1.continuous_contract, start=m1.start,
        end=m1.end, bars=m1.bars, min_years=m1.min_years,
        quality_gate=QualityGateResult(
            status="PASS",
            checks={"bars_non_empty": True, "coverage_years": True},
            detail={"span_years": 3.0},
            run_at="2026-08-19T12:00:00",
        ),
        generated_at=m1.generated_at,
    )
    m2 = DatasetManifest.from_json(m1.to_json())
    assert m2 == m1
    assert m2.quality_gate.status == "PASS"
    assert m2.quality_gate.checks["coverage_years"] is True


def test_write_and_load_manifest(tmp_path: Path):
    asset = by_symbol("AG")
    m = DatasetManifest.build(asset, TimeFrame.H1, _bars(), min_years=3.0)
    path = write_manifest(m, tmp_path)
    assert path == manifest_path(tmp_path, "AG", "1h")
    assert path.exists()
    loaded = load_manifest(path)
    assert loaded.symbol == "AG"
    assert loaded.timeframe == "1h"
