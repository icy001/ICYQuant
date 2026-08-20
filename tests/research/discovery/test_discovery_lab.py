"""Invariant tests for Strategy Discovery Lab v1.

The most important rules under test:

- the Train / Validation / OOS split is sealed and non-overlapping;
- walk-forward windows never touch the OOS segment;
- the candidate generator is deterministic and only emits whitelisted
  structures / parameters;
- the Discovery Gate is fail-closed and wired to every threshold;
- the backtest engine produces sane results on a synthetic trend.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from research.data.bar import Bar
from research.discovery.backtest import (
    BacktestResult,
    DiscoveryBacktest,
    EVALUATORS,
    Metrics,
)
from research.discovery.candidate import Candidate
from research.discovery.cost import CostModel
from research.discovery.gate import DiscoveryGate
from research.discovery.generator import CandidateGenerator
from research.discovery.indicators import ema, donchian, supertrend
from research.discovery.robustness import (
    parameter_stability,
    walk_forward_check,
)
from research.discovery.run import _families_restricted_spec
from research.discovery.spec import (
    DISCOVERY_SPEC_V1,
    FAMILY_NAMES,
    GATE_THRESHOLDS,
    PARAMETER_SPACES,
    STRUCTURES,
)
from research.discovery.split import (
    ACTIVE_SPLIT,
    build_walk_forward_windows,
)


# --------------------------------------------------------------------------- #
# Split isolation                                                              #
# --------------------------------------------------------------------------- #
def test_split_segments_are_disjoint_and_ordered():
    assert ACTIVE_SPLIT.train_end < ACTIVE_SPLIT.val_start
    assert ACTIVE_SPLIT.val_end < ACTIVE_SPLIT.oos_start


def test_walk_forward_windows_never_touch_oos():
    windows = build_walk_forward_windows(ACTIVE_SPLIT)
    assert windows, "expected at least one walk-forward window"
    for w in windows:
        assert w.oos_start > ACTIVE_SPLIT.train_start
        assert w.oos_end <= ACTIVE_SPLIT.val_end, (
            f"window {w.index} OOS end {w.oos_end} leaks past validation "
            f"end {ACTIVE_SPLIT.val_end}"
        )


def test_slice_bars_isolates_segments():
    bars = _hourly_bars(n=200, start=datetime(2023, 1, 1))
    train = ACTIVE_SPLIT.slice_bars(bars, "train")
    val = ACTIVE_SPLIT.slice_bars(bars, "validation")
    oos = ACTIVE_SPLIT.slice_bars(bars, "oos")
    for seg_bars, (lo, hi) in (
        (train, (ACTIVE_SPLIT.train_start, ACTIVE_SPLIT.train_end)),
        (val, (ACTIVE_SPLIT.val_start, ACTIVE_SPLIT.val_end)),
        (oos, (ACTIVE_SPLIT.oos_start, ACTIVE_SPLIT.oos_end)),
    ):
        for b in seg_bars:
            assert lo <= b.timestamp.date() <= hi


# --------------------------------------------------------------------------- #
# Generator reproducibility                                                   #
# --------------------------------------------------------------------------- #
def test_generator_is_deterministic():
    g1 = CandidateGenerator(DISCOVERY_SPEC_V1, seed=42).generate()
    g2 = CandidateGenerator(DISCOVERY_SPEC_V1, seed=42).generate()
    assert [c.candidate_id for c in g1] == [c.candidate_id for c in g2]
    assert [c.parameters for c in g1] == [c.parameters for c in g2]


def test_generator_matches_spec_targets():
    candidates = CandidateGenerator(DISCOVERY_SPEC_V1, seed=42).generate()
    assert len(candidates) == DISCOVERY_SPEC_V1.candidates_total
    counts = DISCOVERY_SPEC_V1.family_target
    got: dict[str, int] = {}
    for c in candidates:
        got[c.family] = got.get(c.family, 0) + 1
    for family in FAMILY_NAMES:
        assert got.get(family, 0) == counts[family]


def test_generator_only_emits_whitelisted_definitions():
    candidates = CandidateGenerator(DISCOVERY_SPEC_V1, seed=42).generate()
    assert candidates
    for c in candidates:
        assert c.structure_id in STRUCTURES
        assert c.structure_id in EVALUATORS
        assert c.family == STRUCTURES[c.structure_id]["family"]
        pool = PARAMETER_SPACES[c.structure_id]
        assert c.parameters in pool, (
            f"{c.candidate_id} parameters {c.parameters} not whitelisted"
        )
        # every declared param key present
        assert set(c.parameters) == set(STRUCTURES[c.structure_id]["params"])


def test_families_restricted_spec():
    spec = _families_restricted_spec(
        DISCOVERY_SPEC_V1, ["Trend", "Momentum", "Breakout"])
    assert spec.candidates_total == 100 + 60 + 60
    assert spec.family_target["Mean Reversion"] == 0
    assert spec.family_target["Hybrid"] == 0
    # everything else stays sealed
    assert spec.gate_thresholds == DISCOVERY_SPEC_V1.gate_thresholds
    assert spec.split == DISCOVERY_SPEC_V1.split
    candidates = CandidateGenerator(spec, seed=42).generate()
    assert len(candidates) == 220
    assert {c.family for c in candidates} == {"Trend", "Momentum", "Breakout"}


# --------------------------------------------------------------------------- #
# Discovery Gate                                                               #
# --------------------------------------------------------------------------- #
def _result(cid: str, asset: str, m: Metrics, n_days: int = 120) -> BacktestResult:
    # varied positive daily returns so the combined Sharpe is computable
    eq = [100_000.0]
    for i in range(1, n_days):
        eq.append(eq[-1] * (1.0 + (0.02 if i % 2 == 0 else 0.01)))
    start = datetime(2023, 1, 1)
    curve = [((start + timedelta(days=i)).date().isoformat(), round(e, 4))
             for i, e in enumerate(eq)]
    return BacktestResult(
        candidate_id=cid, asset=asset, structure_id="trend_ema_cross",
        segment="test", start=datetime(2023, 1, 1),
        end=datetime(2023, 12, 31), cost_one_way_bps=5.0, metrics=m,
        equity_curve=curve,
    )


def _good_metrics() -> Metrics:
    return Metrics(total_return=0.2, sharpe=2.0, max_drawdown=-0.10,
                   profit_factor=2.0, trade_count=50)


def test_gate_passes_when_all_thresholds_met():
    from research.discovery.robustness import (
        StabilityReport, WalkForwardReport,
    )
    cand = Candidate.build("C0001", "trend_ema_cross",
                           {"fast": 20, "slow": 60}, "NVDA")
    stability = StabilityReport(
        candidate_id="C0001", structure_id="trend_ema_cross", asset="NVDA",
        neighbor_count=10, neighbor_positive_frac=0.8, cv=0.3, passed=True)
    wf = WalkForwardReport(
        candidate_id="C0001", asset="NVDA", windows_total=6,
        windows_positive=5, passed=True)
    outcome = DiscoveryGate().evaluate(
        cand, True,
        _result("C0001", "NVDA", _good_metrics()),
        _result("C0001", "NVDA", _good_metrics()),
        _result("C0001", "NVDA", _good_metrics()),
        stability, wf,
        {"commission_bps": 0.0, "spread_bps": 2.0, "slippage_bps": 3.0},
    )
    assert outcome.passed, [c.detail for c in outcome.checks if not c.passed]
    assert len(outcome.checks) == 16


def test_gate_is_fail_closed_on_empty_data():
    cand = Candidate.build("C0002", "trend_ema_cross",
                           {"fast": 20, "slow": 60}, "NVDA")
    empty = BacktestResult(
        candidate_id="C0002", asset="NVDA", structure_id="trend_ema_cross",
        segment="train", start=None, end=None, cost_one_way_bps=0.0)
    from research.discovery.robustness import (
        StabilityReport, WalkForwardReport,
    )
    outcome = DiscoveryGate().evaluate(
        cand, False, empty, empty, empty,
        StabilityReport(candidate_id="C0002",
                        structure_id="trend_ema_cross", asset="NVDA"),
        WalkForwardReport(candidate_id="C0002", asset="NVDA"),
        {"commission_bps": 0.0, "spread_bps": 0.0, "slippage_bps": 0.0},
    )
    assert not outcome.passed
    assert outcome.fail_reason == "dataset_gate"


def test_gate_rejects_oos_sharpe_below_threshold():
    from research.discovery.robustness import (
        StabilityReport, WalkForwardReport,
    )
    cand = Candidate.build("C0003", "trend_ema_cross",
                           {"fast": 20, "slow": 60}, "NVDA")
    weak = _good_metrics()
    weak.sharpe = GATE_THRESHOLDS["min_sharpe"] - 0.01
    stability = StabilityReport(
        candidate_id="C0003", structure_id="trend_ema_cross", asset="NVDA",
        neighbor_count=10, neighbor_positive_frac=0.8, cv=0.3, passed=True)
    wf = WalkForwardReport(
        candidate_id="C0003", asset="NVDA", windows_total=6,
        windows_positive=5, passed=True)
    outcome = DiscoveryGate().evaluate(
        cand, True,
        _result("C0003", "NVDA", _good_metrics()),
        _result("C0003", "NVDA", _good_metrics()),
        _result("C0003", "NVDA", weak),
        stability, wf,
        {"commission_bps": 0.0, "spread_bps": 2.0, "slippage_bps": 3.0},
    )
    assert not outcome.passed
    assert outcome.fail_reason == "oos_performance"


# --------------------------------------------------------------------------- #
# Robustness checks                                                            #
# --------------------------------------------------------------------------- #
def test_parameter_stability_rejects_magic_point():
    # lone spike among weak/negative neighbours -> high CV -> fail
    report = parameter_stability(
        "C0001", "trend_ema_cross", "NVDA",
        [0.10, -0.20, 2.87, 0.05],
        min_positive_frac=0.5, max_cv=1.5)
    assert not report.passed


def test_parameter_stability_rejects_mostly_negative_neighbourhood():
    report = parameter_stability(
        "C0001", "trend_ema_cross", "NVDA",
        [-0.5, -0.2, 0.1, -0.8, -0.3, 0.05],
        min_positive_frac=0.5, max_cv=1.5)
    assert not report.passed  # positive fraction 2/6 < 0.5


def test_parameter_stability_accepts_plateau():
    # the user's "good" pattern: neighbours all near the same Sharpe
    report = parameter_stability(
        "C0001", "trend_ema_cross", "NVDA",
        [1.51, 1.48, 1.49, 1.46, 1.47, 1.50],
        min_positive_frac=0.5, max_cv=1.5)
    assert report.passed


def test_parameter_stability_fails_closed_without_neighbours():
    report = parameter_stability(
        "C0001", "trend_ema_cross", "NVDA", [])
    assert not report.passed


def test_walk_forward_check_requires_two_thirds_positive():
    r_pos = _result("C0001", "NVDA", _good_metrics())
    r_neg = _result("C0001", "NVDA", _good_metrics())
    r_neg.metrics.total_return = -0.05
    ok = walk_forward_check("C0001", "NVDA",
                            [r_pos] * 4 + [r_neg] * 2, min_positive_frac=0.66)
    assert ok.passed
    bad = walk_forward_check("C0001", "NVDA",
                             [r_pos] * 2 + [r_neg] * 4, min_positive_frac=0.66)
    assert not bad.passed


# --------------------------------------------------------------------------- #
# Indicators (no look-ahead)                                                   #
# --------------------------------------------------------------------------- #
def test_ema_warmup_and_alignment():
    closes = [float(i) for i in range(1, 51)]
    out = ema(closes, 10)
    assert len(out) == len(closes)
    assert out[:8] == [None] * 8
    assert out[9] is not None


def test_supertrend_bullish_on_uptrend():
    closes = [100.0 + i for i in range(60)]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    st = supertrend(highs, lows, closes, 10, 3.0)
    assert st[-1] is True


def test_donchian_excludes_current_bar():
    # constant series: channel from previous bars equals the constant,
    # so a breakout requires the current bar to exceed prior history only
    highs = [100.0] * 30 + [110.0, 110.0]
    lows = [100.0] * 30 + [110.0, 110.0]
    upper, middle, lower = donchian(highs, lows, 20)
    assert upper[29] == 100.0  # uses bars 9..28, not bar 29
    assert upper[30] == 100.0  # current bar (110) excluded — no look-ahead
    assert upper[31] == 110.0  # bar 30 is inside the window now


def test_indicator_library_facade_covers_all_methods():
    """Every facade method must run without NameError (regression: the
    Donchian facade once referenced an undefined ``closes`` in its key)."""
    from research.discovery.indicators import IndicatorLibrary
    closes = [100.0 + i * 0.5 for i in range(80)]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    lib = IndicatorLibrary()
    assert len(lib.ema(closes, 10)) == 80
    assert len(lib.sma(closes, 10)) == 80
    assert len(lib.atr(highs, lows, closes, 14)) == 80
    assert len(lib.supertrend(highs, lows, closes, 10, 3.0)) == 80
    u, m, l = lib.bollinger(closes, 20, 2.0)
    assert len(u) == 80
    assert len(lib.rsi(closes, 14)) == 80
    assert len(lib.roc(closes, 14)) == 80
    assert len(lib.momentum(closes, 14)) == 80
    line, sig, hist = lib.macd(closes, 12, 26, 9)
    assert len(line) == 80
    k, d = lib.stochastic(highs, lows, closes, 14)
    assert len(k) == 80
    assert len(lib.adx(highs, lows, closes, 14)) == 80
    du, dm, dl = lib.donchian(highs, lows, 20)
    assert len(du) == 80
    assert len(lib.rolling_high(highs, 20)) == 80
    assert len(lib.rolling_low(lows, 20)) == 80
    assert len(lib.historical_volatility(closes, 20)) == 80


# --------------------------------------------------------------------------- #
# Backtest engine sanity                                                       #
# --------------------------------------------------------------------------- #
def _hourly_bars(n: int, start: datetime, base: float = 100.0,
                 slope: float = 0.2) -> list[Bar]:
    bars: list[Bar] = []
    price = base
    ts = start
    for _ in range(n):
        o = price
        price = price + slope
        c = price
        bars.append(Bar(symbol="TEST", timestamp=ts, open=o,
                        high=max(o, c) + 0.05, low=min(o, c) - 0.05,
                        close=c, volume=1000.0))
        ts += timedelta(hours=1)
    return bars


def _flat_split():
    from research.discovery.split import build_split
    from research.discovery.spec import SPLIT_CONFIG
    return build_split(SPLIT_CONFIG)


def test_backtest_enters_and_holds_on_uptrend():
    bars = _hourly_bars(600, datetime(2023, 1, 2))
    cand = Candidate.build("C0001", "trend_ema_cross",
                           {"fast": 5, "slow": 20}, "NVDA")
    bt = DiscoveryBacktest(cost_model=CostModel(
        {"NVDA": {"commission_bps": 0.0, "spread_bps": 0.1, "slippage_bps": 0.1}}))
    split = _flat_split()
    train = bt.run(bars, cand, split, "train")
    # monotone uptrend: one entry held to the segment end
    assert train.metrics.trade_count >= 1
    assert train.metrics.total_return > 0
    assert train.metrics.exposure > 0.5


def test_backtest_costs_reduce_equity():
    bars = _hourly_bars(600, datetime(2023, 1, 2))
    cand = Candidate.build("C0001", "trend_ema_cross",
                           {"fast": 5, "slow": 20}, "NVDA")
    cheap = DiscoveryBacktest(cost_model=CostModel(
        {"NVDA": {"commission_bps": 0.0, "spread_bps": 0.1, "slippage_bps": 0.1}}))
    dear = DiscoveryBacktest(cost_model=CostModel(
        {"NVDA": {"commission_bps": 10.0, "spread_bps": 40.0, "slippage_bps": 50.0}}))
    split = _flat_split()
    r_cheap = cheap.run(bars, cand, split, "train")
    r_dear = dear.run(bars, cand, split, "train")
    assert r_cheap.metrics.total_return > r_dear.metrics.total_return
    assert r_dear.cost_one_way_bps == 100.0


def test_backtest_unknown_structure_raises():
    bars = _hourly_bars(10, datetime(2023, 1, 2))
    bad = Candidate(
        candidate_id="C0009", family="Trend", structure_id="nope",
        parameters={}, asset="NVDA", timeframe="1H")
    with pytest.raises(ValueError):
        DiscoveryBacktest().run(bars, bad, _flat_split(), "train")
