"""Invariant tests for the Factor Discovery Track (Alpha101).

The most important rules under test:

- every one of the 101 WorldQuant formulas is computable on synthetic data
  and strictly causal (no look-ahead: truncating the future never changes
  the past);
- the delay-1 IC alignment is correct (a perfect predictor gets IC = 1);
- the long-short backtest applies costs exactly and positions earn the
  *next* bar's return;
- the 16-item Factor Gate is fail-closed and wired to every threshold;
- the engine + report produce the four-table output end-to-end on a
  synthetic dataset.
"""
from __future__ import annotations

import csv
import json
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from research.discovery.factor.evaluation import (
    align_factor_returns,
    pearson,
    segment_ic,
    spearman,
)
from research.discovery.factor.factor_backtest import (
    net_returns,
    portfolio_metrics,
    positions_from_z,
    rolling_zscore,
)
from research.discovery.factor.factor_engine import FactorDiscoveryEngine
from research.discovery.factor.factor_gate import FactorGate, PairEvidence
from research.discovery.factor.factor_report import FactorReport
from research.discovery.factor.factor_spec import (
    ALPHA_SCORE_WEIGHTS,
    FACTOR_SPEC_V1,
    FACTOR_GATE_THRESHOLDS,
)
from research.discovery.factor.formulas import (
    ALPHA_IDS,
    MarketData,
    compute_alpha,
)
from research.discovery.factor.operators import (
    correlation,
    decay_linear,
    delay,
    delta,
    rank,
    scale,
    stddev,
    ts_argmax,
    ts_max,
    ts_mean,
    ts_min,
    ts_rank,
)


# --------------------------------------------------------------------------- #
# Spec sanity                                                                  #
# --------------------------------------------------------------------------- #
def test_spec_is_sealed():
    assert FACTOR_SPEC_V1.universe == (
        "NVDA", "SPY", "QQQ", "000688.SH", "HSTECH",
        "EURUSD", "XAUUSD", "AU", "AG")
    assert FACTOR_SPEC_V1.alphas_total == 101
    assert len(ALPHA_IDS) == 101
    assert ALPHA_IDS[0] == "Alpha001" and ALPHA_IDS[-1] == "Alpha101"
    # score weights: positive pair weights sum to 1 (turnover is a penalty),
    # alpha weights sum to 1
    pos = [w for w in FACTOR_SPEC_V1.score_weights.values() if w > 0]
    assert abs(sum(pos) - 1.0) < 1e-9
    assert FACTOR_SPEC_V1.score_weights["turnover_penalty"] < 0
    assert abs(sum(ALPHA_SCORE_WEIGHTS.values()) - 1.0) < 1e-9


# --------------------------------------------------------------------------- #
# Operators                                                                    #
# --------------------------------------------------------------------------- #
def test_ts_rank_matches_direct_percentile():
    x = [3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0]
    d = 4
    out = ts_rank(x, d)
    # first d-1 bars are warm-up
    assert out[: d - 1] == [None] * (d - 1)
    for i in range(d - 1, len(x)):
        window = sorted(x[i - d + 1: i + 1])
        v = x[i]
        lo = sum(1 for w in window if w < v)      # strictly below
        le = sum(1 for w in window if w <= v)     # below or equal
        # midpoint percentile: (avg 0-based rank + 0.5) / d -> (0.5/d, 1-0.5/d)
        expected = ((lo + le) / 2.0) / d
        assert out[i] == pytest.approx(expected)


def test_rank_is_rolling_percentile_adaptation():
    x = [float(i % 7) for i in range(300)]
    assert rank(x, window=50) == ts_rank(x, 50)


def test_rank_and_scale_tolerate_sparse_windows():
    """rank()/scale() must stay computable when ~30% of the input bars are
    None (e.g. nested correlation chains with degenerate windows)."""
    random.seed(23)
    x = [None if random.random() < 0.3 else random.gauss(0, 1)
         for _ in range(600)]
    r = rank(x, window=100)
    s = scale(x, window=100)
    r_vals = [v for v in r if v is not None]
    s_vals = [v for v in s if v is not None]
    assert r_vals, "rank returned nothing on a sparse series"
    assert s_vals, "scale returned nothing on a sparse series"
    assert all(0.0 < v < 1.0 for v in r_vals)
    # strictly below the coverage floor -> None
    mostly_none = [None] * 99 + [1.0]
    assert rank(mostly_none, window=100)[-1] is None


def test_delay_and_delta():
    x = [10.0, 11.0, 12.0, 13.0]
    assert delay(x, 2) == [None, None, 10.0, 11.0]
    assert delta(x, 1) == [None, 1.0, 1.0, 1.0]


def test_ts_mean_and_stddev_warmup():
    x = [1.0, 2.0, 3.0, 4.0]
    m = ts_mean(x, 3)
    assert m[:2] == [None, None]
    assert m[2] == pytest.approx(2.0)
    assert m[3] == pytest.approx(3.0)
    s = stddev(x, 3)
    assert s[:2] == [None, None]
    assert s[2] == pytest.approx(math.sqrt(2.0 / 3.0))


def test_ts_min_max_argmax():
    x = [5.0, 3.0, 8.0, 1.0, 4.0]
    assert ts_max(x, 3) == [None, None, 8.0, 8.0, 8.0]
    assert ts_min(x, 3) == [None, None, 3.0, 1.0, 1.0]
    am = ts_argmax(x, 3)
    # offset from the newest bar: max of (8,1,4) is 8 at offset 2
    assert am[4] == 2.0


def test_correlation_matches_direct_computation():
    random.seed(7)
    x = [random.gauss(0, 1) for _ in range(80)]
    y = [0.5 * v + random.gauss(0, 0.3) for v in x]
    d = 20
    out = correlation(x, y, d)
    assert out[: d - 1] == [None] * (d - 1)
    from research.discovery.factor.evaluation import pearson as _p
    for i in (d - 1, 40, 79):
        expected = _p(x[i - d + 1: i + 1], y[i - d + 1: i + 1])
        assert out[i] == pytest.approx(expected, abs=1e-9)


def test_decay_linear_weights():
    x = [1.0, 2.0, 3.0]
    out = decay_linear(x, 3)
    # weights 1,2,3 oldest->newest, sum 6 -> (1*1 + 2*2 + 3*3)/6
    assert out[2] == pytest.approx(14.0 / 6.0)


def test_div_zero_denominator_is_none_not_a_crash():
    """Real data hits zero denominators (close == low, vwap == close, ...):
    the bar must be None (locally not computable), never a crash."""
    from research.discovery.factor.operators import div
    out = div([1.0, 2.0, 3.0], [2.0, 0.0, 4.0])
    assert out == [0.5, None, 0.75]


def test_scale_normalises_magnitude():
    x = [1.0, -1.0, 2.0, -2.0] * 10
    out = scale(x, window=8)
    assert out[:7] == [None] * 7
    # mean |x| over any full window = 1.5 -> values scaled by 1/1.5
    assert out[7] == pytest.approx(-2.0 / 1.5)
    assert out[8] == pytest.approx(1.0 / 1.5)


# --------------------------------------------------------------------------- #
# No look-ahead (operators are causal)                                         #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("fn", [
    lambda md_x: ts_rank(md_x, 20),
    lambda md_x: ts_mean(md_x, 10),
    lambda md_x: ts_max(md_x, 10),
    lambda md_x: correlation(md_x, [v * 0.5 + 1.0 for v in md_x], 10),
    lambda md_x: decay_linear(md_x, 8),
    lambda md_x: stddev(md_x, 12),
])
def test_operators_are_causal(fn):
    random.seed(11)
    x = [random.gauss(0, 1) for _ in range(60)]
    full = fn(x)
    cut = 40
    truncated = fn(x[:cut])
    assert full[:cut] == truncated


# --------------------------------------------------------------------------- #
# Formulas                                                                     #
# --------------------------------------------------------------------------- #
def _synthetic_md(n: int = 4000, seed: int = 42) -> MarketData:
    rng = random.Random(seed)
    price = 100.0
    o: list[float] = []
    h: list[float] = []
    l: list[float] = []
    c: list[float] = []
    v: list[float] = []
    for _ in range(n):
        ret = rng.gauss(0.0, 0.004)
        open_ = price
        price = max(1.0, price * (1.0 + ret))
        close = price
        o.append(open_)
        c.append(close)
        h.append(max(open_, close) * (1.0 + abs(rng.gauss(0.0, 0.001))))
        l.append(min(open_, close) * (1.0 - abs(rng.gauss(0.0, 0.001))))
        v.append(max(1.0, rng.gauss(10_000.0, 2_000.0)))
    return MarketData(open_=o, high=h, low=l, close=c, volume=v)


def test_all_101_formulas_compute_without_error():
    md = _synthetic_md()
    for alpha_id in ALPHA_IDS:
        factor = compute_alpha(alpha_id, md)
        assert len(factor) == len(md.close), alpha_id
        values = [v for v in factor if v is not None]
        assert values, f"{alpha_id} produced no computable values"
        assert all(v == v for v in values), (
            f"{alpha_id} leaked NaN (must be None instead)")


@pytest.mark.parametrize("alpha_id", ALPHA_IDS[::10] + ["Alpha101"])
def test_formulas_are_causal(alpha_id):
    """Truncating the future must never change the factor's past values."""
    md = _synthetic_md(n=1200, seed=3)
    full = compute_alpha(alpha_id, md)
    cut = 800
    md_trunc = MarketData(
        open_=md.open[:cut], high=md.high[:cut], low=md.low[:cut],
        close=md.close[:cut], volume=md.volume[:cut])
    truncated = compute_alpha(alpha_id, md_trunc)
    for t in range(cut):
        assert full[t] == truncated[t], (
            f"{alpha_id} looks ahead at bar {t}")


# --------------------------------------------------------------------------- #
# IC evaluation                                                                #
# --------------------------------------------------------------------------- #
def test_pearson_and_spearman_basics():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert pearson(xs, [2.0 * v + 1.0 for v in xs]) == pytest.approx(1.0)
    assert pearson(xs, [-v for v in xs]) == pytest.approx(-1.0)
    # monotone non-linear -> spearman 1, pearson < 1
    ys = [v ** 3 for v in xs]
    assert spearman(xs, ys) == pytest.approx(1.0)
    assert pearson(xs, ys) < 1.0


def test_perfect_delay1_predictor_gets_ic_one():
    md = _synthetic_md(n=600, seed=5)
    n = len(md.close)
    bar_returns: list[float | None] = [None] * n
    for i in range(1, n):
        bar_returns[i] = md.close[i] / md.close[i - 1] - 1.0
    indices = list(range(n))
    # factor[t] = return of bar t -> t+1 (delay-1 perfect predictor)
    factor: list[float | None] = [None] * n
    for t in range(n - 1):
        factor[t] = bar_returns[t + 1]
    fs, rs = align_factor_returns(factor, bar_returns, indices)
    assert len(fs) == n - 1
    seg = segment_ic(factor, bar_returns, indices)
    assert seg.ic == pytest.approx(1.0, abs=1e-9)
    assert seg.rank_ic == pytest.approx(1.0, abs=1e-9)
    assert seg.block_count >= 2


def test_segment_ic_fail_closed_on_short_data():
    seg = segment_ic([1.0, 2.0], [0.01, 0.01], [0, 1])
    assert seg.ic is None
    assert seg.block_count == 0


# --------------------------------------------------------------------------- #
# Factor backtest                                                              #
# --------------------------------------------------------------------------- #
def test_rolling_zscore_warmup_and_clip():
    x = [1.0] * 300 + [100.0]
    z = rolling_zscore(x, window=50, clip=3.0)
    assert z[:49] == [None] * 49
    # constant window -> zero variance -> z is undefined (None, fail-closed)
    assert z[49] is None
    assert z[300] == 3.0  # clipped at +3


def test_orient_positions_by_train_ic_sign():
    from research.discovery.factor.factor_backtest import orient_positions
    pos = [0.0, 1.0, 1.0, -1.0]
    # positive train IC -> keep direction
    assert orient_positions(pos, 0.05) == ([0.0, 1.0, 1.0, -1.0], 1.0)
    # negative train IC -> flip (direction-agnostic |IC|, direction-aware book)
    assert orient_positions(pos, -0.05) == ([0.0, -1.0, -1.0, 1.0], -1.0)
    # no measurable direction -> flat, fail closed
    assert orient_positions(pos, None) == ([0.0] * 4, 0.0)
    assert orient_positions(pos, 0.0) == ([0.0] * 4, 0.0)


def test_positions_schmitt_trigger_hysteresis():
    z = [None, 1.5, 0.5, 0.3, 0.1, -0.2, -1.5, -0.3, -0.2, 0.5]
    pos = positions_from_z(z, entry=1.0, exit_=0.25)
    # hysteresis: +1 until z < 0.25; short from -1.5 until z > -0.25
    assert pos == [0.0, 1.0, 1.0, 1.0, 0.0, 0.0, -1.0, -1.0, 0.0, 0.0]


def test_net_returns_cost_accounting():
    closes = [100.0, 100.0, 100.0, 100.0]
    positions = [0.0, 1.0, 1.0, 0.0]
    cost = 0.001
    net = net_returns(closes, positions, cost)
    assert net[0] is None
    assert net[1] == pytest.approx(-cost)          # entry cost
    assert net[2] == pytest.approx(0.0)            # hold, no cost, no return
    assert net[3] == pytest.approx(-cost)          # exit cost


def test_positions_earn_next_bar_return():
    closes = [100.0, 110.0, 121.0]
    positions = [1.0, 1.0, 1.0]
    net = net_returns(closes, positions, 0.0)
    # pos[t-1] * ret[t]: pos decided at bar t-1 earns bar t's return
    assert net[1] == pytest.approx(0.10)
    assert net[2] == pytest.approx(0.10)


def test_portfolio_metrics_compounds_segment():
    dates = [datetime(2023, 1, d).date() for d in range(1, 6)]
    net = [None, 0.10, 0.10, -0.05, 0.10]
    idx = list(range(5))
    positions = [0.0, 1.0, 1.0, 0.0, 0.0]  # one full round trip
    m = portfolio_metrics(dates, net, positions, idx)
    assert m.total_return == pytest.approx(1.1 * 1.1 * 0.95 * 1.1 - 1.0)
    assert m.turnover_per_bar == pytest.approx(2.0 / 5.0)
    assert m.trade_count == 1  # round trips: (entries + exits) / 2
    assert m.exposure == pytest.approx(2.0 / 5.0)


def test_portfolio_metrics_daily_sharpe_and_drawdown():
    """Regression: daily returns are within-day compounded P&L, not the
    ratio of consecutive days' intraday products (which has mean ~ 0 and
    destroyed every Sharpe); drawdown is on cumulative daily equity."""
    dates = [datetime(2023, 1, 1).date()] * 2 + \
            [datetime(2023, 1, 2).date()] * 2 + \
            [datetime(2023, 1, 3).date()] * 2 + \
            [datetime(2023, 1, 4).date()] * 2
    # day 1..4 compounded: +2.01%, +2.01%, -1.00%, +2.01%
    net = [0.01, 0.01, 0.01, 0.01, -0.005, -0.005, 0.01, 0.01]
    idx = list(range(8))
    positions = [1.0] * 8
    m = portfolio_metrics(dates, net, positions, idx)
    # a book earning ~+1.2%/day on ~1.5%/day vol must be a high-Sharpe book
    assert m.sharpe > 5.0
    # drawdown happens only on day 3: eq 1.0406 -> 1.03023
    assert m.max_drawdown == pytest.approx(-0.00997, abs=1e-4)


# --------------------------------------------------------------------------- #
# Factor Gate (fail-closed)                                                    #
# --------------------------------------------------------------------------- #
def _evidence(**overrides) -> PairEvidence:
    from research.discovery.factor.evaluation import SegmentIC
    from research.discovery.factor.factor_backtest import PortfolioMetrics
    ev = PairEvidence(
        dataset_ok=True,
        coverage=0.95,
        train_ic=SegmentIC(ic=0.05, rank_ic=0.05, icir=0.6, block_count=6),
        validation_ic=SegmentIC(ic=0.03),
        oos_ic=SegmentIC(ic=0.03, icir=0.5, block_count=3),
        train_pf=PortfolioMetrics(sharpe=1.0, total_return=0.2),
        validation_pf=PortfolioMetrics(sharpe=0.8, total_return=0.05),
        oos_pf=PortfolioMetrics(sharpe=1.0, total_return=0.1,
                                max_drawdown=-0.1, turnover_per_bar=0.1),
        wf_windows_total=6,
        wf_windows_positive=5,
        stability_frac=1.0,
        one_way_bps=5.0,
        slippage_bps=2.0,
    )
    for k, v in overrides.items():
        setattr(ev, k, v)
    return ev


def test_gate_has_16_checks_and_passes_good_evidence():
    out = FactorGate().evaluate("Alpha001", "NVDA", _evidence())
    assert len(out.checks) == 16
    assert [c.name for c in out.checks] == list(FactorGate.CHECK_NAMES)
    assert out.passed, [c.detail for c in out.checks if not c.passed]
    assert out.fail_reason == ""


def test_gate_fail_closed_on_missing_dataset():
    ev = _evidence(dataset_ok=False)
    out = FactorGate().evaluate("Alpha001", "NVDA", ev)
    assert not out.passed
    assert out.fail_reason == "dataset_gate"


def test_gate_rejects_weak_train_icir():
    from research.discovery.factor.evaluation import SegmentIC
    ev = _evidence(train_ic=SegmentIC(ic=0.05, rank_ic=0.05,
                                      icir=0.10, block_count=6))
    out = FactorGate().evaluate("Alpha001", "NVDA", ev)
    assert not out.passed
    assert out.fail_reason == "train_icir"


def test_gate_rejects_validation_sign_flip():
    from research.discovery.factor.evaluation import SegmentIC
    ev = _evidence(validation_ic=SegmentIC(ic=-0.03))
    out = FactorGate().evaluate("Alpha001", "NVDA", ev)
    assert not out.passed
    assert out.fail_reason == "validation_performance"


def test_gate_rejects_oos_sharpe_below_threshold():
    from research.discovery.factor.factor_backtest import PortfolioMetrics
    ev = _evidence(oos_pf=PortfolioMetrics(
        sharpe=FACTOR_GATE_THRESHOLDS["min_oos_sharpe"] - 0.01,
        total_return=0.1, max_drawdown=-0.1, turnover_per_bar=0.1))
    out = FactorGate().evaluate("Alpha001", "NVDA", ev)
    assert not out.passed
    assert out.fail_reason == "oos_performance"


def test_gate_rejects_when_walk_forward_missing():
    ev = _evidence(wf_windows_total=0, wf_windows_positive=0)
    out = FactorGate().evaluate("Alpha001", "NVDA", ev)
    assert not out.passed
    assert out.fail_reason == "walk_forward"


def test_gate_rejects_unstable_factor():
    ev = _evidence(stability_frac=0.5)
    out = FactorGate().evaluate("Alpha001", "NVDA", ev)
    assert not out.passed
    assert out.fail_reason == "stability"


# --------------------------------------------------------------------------- #
# Engine + report end-to-end on a synthetic dataset                            #
# --------------------------------------------------------------------------- #
def _write_synthetic_csv(path: Path, symbol: str = "NVDA",
                         n_bars: int = 26_000) -> None:
    rng = random.Random(42)
    ts = datetime(2023, 1, 1)
    price = 100.0
    rows = []
    for _ in range(n_bars):
        ret = rng.gauss(0.0, 0.003)
        open_ = price
        price = max(1.0, price * (1.0 + ret))
        close = price
        high = max(open_, close) * (1.0 + abs(rng.gauss(0.0, 0.0005)))
        low = min(open_, close) * (1.0 - abs(rng.gauss(0.0, 0.0005)))
        rows.append({
            "timestamp": ts.isoformat(),
            "open": f"{open_:.6f}",
            "high": f"{high:.6f}",
            "low": f"{low:.6f}",
            "close": f"{close:.6f}",
            "volume": f"{max(1.0, rng.gauss(10_000.0, 1_000.0)):.2f}",
        })
        ts += timedelta(hours=1)
    path.write_text(
        "\n".join(["timestamp,open,high,low,close,volume"] +
                  [f"{r['timestamp']},{r['open']},{r['high']},{r['low']},"
                   f"{r['close']},{r['volume']}" for r in rows]) + "\n",
        encoding="utf-8")


@pytest.fixture(scope="module")
def synthetic_engine_run(tmp_path_factory):
    data_root = tmp_path_factory.mktemp("factor_data")
    _write_synthetic_csv(data_root / "NVDA_1h.csv")
    engine = FactorDiscoveryEngine(spec=FACTOR_SPEC_V1,
                                   data_root=data_root, jobs=1)
    result = engine.run_experiment("factor-test", limit_alphas=5,
                                   assets=["NVDA"])
    return result


def test_engine_runs_all_pairs_and_builds_matrix(synthetic_engine_run):
    result = synthetic_engine_run
    assert result.pairs_backtested == 5
    assert set(result.outcomes) == set(ALPHA_IDS[:5])
    for alpha_id, per_asset in result.outcomes.items():
        for asset, od in per_asset.items():
            assert len(od["checks"]) == 16
            # gate verdict consistent with the checks
            assert od["passed"] == all(c["passed"] for c in od["checks"])
    matrix = result.cross_asset_matrix
    assert matrix["assets"] == ["NVDA"]
    assert set(matrix["icir"]) == set(ALPHA_IDS[:5])
    assert result.alpha_summary and len(result.alpha_summary) == 5


def test_engine_is_deterministic(synthetic_engine_run, tmp_path_factory):
    data_root = synthetic_engine_run.spec and None  # noqa: F841 (placeholder)
    # rerun on the same synthetic csv -> identical outcomes
    root = tmp_path_factory.mktemp("factor_data_2")
    _write_synthetic_csv(root / "NVDA_1h.csv")
    engine = FactorDiscoveryEngine(spec=FACTOR_SPEC_V1, data_root=root,
                                   jobs=1)
    rerun = engine.run_experiment("factor-test-2", limit_alphas=5,
                                  assets=["NVDA"])
    assert (rerun.outcomes == synthetic_engine_run.outcomes)


def test_report_contains_the_four_tables(synthetic_engine_run, tmp_path):
    result = synthetic_engine_run
    # a fake strategy report so the convergence table has a partner
    strategy_report = tmp_path / "strategy_report.json"
    strategy_report.write_text(json.dumps({
        "experiment_id": "lab-v1",
        "funnel": {"final_candidates": 1},
        "top_candidates_detail": [{
            "candidate_id": "C0001",
            "family": "Trend",
            "structure_id": "trend_ema_cross",
            "params": {"fast": 20, "slow": 60},
            "assets": ["NVDA"],
            "total_score": 0.8,
        }],
    }), encoding="utf-8")

    report = FactorReport(output_dir=tmp_path, spec=FACTOR_SPEC_V1)
    data = report.build(result, strategy_report_path=strategy_report)
    assert len(data["alpha_ranking"]) == 5
    # alpha ranking is ordered by score
    scores = [r["score"] for r in data["alpha_ranking"]]
    assert scores == sorted(scores, reverse=True)
    assert data["alpha_ranking"][0]["rank"] == 1

    md = report.to_markdown(data)
    assert "Factor Gate v1 Funnel" in md
    assert "## ② Alpha Ranking" in md
    assert "## ③ Cross-Asset Alpha Matrix" in md
    assert "## ④ Strategy x Factor Candidates" in md
    # every one of the 5 alphas appears in the cross-asset matrix
    for alpha_id in ALPHA_IDS[:5]:
        assert alpha_id in md
    # convergence references the strategy experiment
    assert "lab-v1" in md
    # no factor passed the gate -> watch-list pairings must be PROVISIONAL
    combos = data["convergence"]["combinations"]
    assert combos, "expected PROVISIONAL combos from the watch list"
    assert all(c["status"] == "PROVISIONAL" for c in combos)
    assert all(c["next_step"] == "WATCH_LIST" for c in combos)
    assert all("NVDA" in c["shared_assets"] for c in combos)

    # JSON round-trips
    json.dumps(data)

    # save() writes both artifacts
    json_path, md_path = report.save(data, "factor-test-report")
    assert json_path.exists() and md_path.exists()
    assert json.loads(json_path.read_text())["experiment_id"] == "factor-test"


# --------------------------------------------------------------------------- #
# CSV export (offline analysis)                                                #
# --------------------------------------------------------------------------- #
def _minimal_report() -> dict:
    """Two pairs: one gate-passed, one rejected at train_ic."""
    def checks(passed: bool) -> list[dict]:
        return [
            {"name": "dataset_gate", "passed": True,
             "detail": "bars loaded and segments non-empty"},
            {"name": "factor_computable", "passed": True,
             "detail": "coverage=0.99 >= 0.8, train blocks=76 >= 2"},
            {"name": "train_ic", "passed": passed,
             "detail": "train IC=-0.4326" if passed else "train IC=-0.001"},
            {"name": "train_rank_ic", "passed": passed,
             "detail": "train RankIC=-0.4359"},
            {"name": "train_icir", "passed": passed,
             "detail": "train ICIR=-6.938"},
            {"name": "train_performance", "passed": passed,
             "detail": "train LS sharpe=23.26 >= 0.5"},
            {"name": "validation_performance", "passed": passed,
             "detail": "val IC=-0.4245, val LS return=254.31%"},
            {"name": "oos_performance", "passed": passed,
             "detail": "oos IC=-0.4399, oos LS sharpe=26.66 >= 0.5"},
            {"name": "max_drawdown", "passed": passed,
             "detail": "oos max_dd=-0.46% >= -50%"},
            {"name": "turnover_cap", "passed": passed,
             "detail": "oos turnover/bar=0.117 <= 0.5"},
            {"name": "walk_forward", "passed": passed,
             "detail": "wf windows positive=6/6 (frac=1.00)"},
            {"name": "stability", "passed": passed,
             "detail": "quarter sign consistency=1.0"},
            {"name": "no_lookahead", "passed": True,
             "detail": "delay-1 alignment: factor[t] predicts return t->t+1 only"},
            {"name": "oos_isolated", "passed": True,
             "detail": "OOS used only for the final measurement"},
            {"name": "transaction_cost", "passed": True,
             "detail": "one-way cost=1.5 bps"},
            {"name": "slippage", "passed": True,
             "detail": "slippage=0.5 bps"},
        ]

    oos = {"ic": -0.4399, "rank_ic": -0.4402, "icir": -5.8224,
           "sharpe": 26.6595, "total_return": 13.136682,
           "max_drawdown": -0.004593, "turnover_per_bar": 0.117018,
           "trade_count": 366, "blocks": 52}
    return {
        "experiment_id": "factor-test",
        "alpha_ranking": [
            {"rank": 1, "alpha_id": "Alpha008", "status": "CANDIDATE",
             "assets_passed_count": 1, "assets_passed": ["EURUSD"],
             "breadth": 1 / 9, "mean_oos_ic": -0.44, "mean_oos_rank_ic": -0.44,
             "mean_oos_icir": -5.82, "mean_oos_sharpe": 26.66,
             "mean_turnover": 0.117, "score": 0.97},
            {"rank": 2, "alpha_id": "Alpha009", "status": "REJECTED",
             "assets_passed_count": 0, "assets_passed": [], "breadth": 0.0,
             "mean_oos_ic": -0.001, "mean_oos_rank_ic": -0.001,
             "mean_oos_icir": -0.01, "mean_oos_sharpe": 0.0,
             "mean_turnover": 0.1, "score": 0.10},
        ],
        "pair_ranking": [
            {"alpha_id": "Alpha008", "asset": "EURUSD", "rank": 1,
             "score": 0.97},
        ],
        "outcomes": {
            "Alpha008": {"EURUSD": {"passed": True, "fail_reason": "",
                                    "checks": checks(True),
                                    "oos_metrics": oos}},
            "Alpha009": {"NVDA": {"passed": False, "fail_reason": "train_ic",
                                  "checks": checks(False),
                                  "oos_metrics": oos}},
        },
        "convergence": {"combinations": [{
            "label": "momentum_macd + Alpha008",
            "strategy_id": "C0145",
            "strategy_structure": "momentum_macd",
            "strategy_params": {"fast": 9, "slow": 21},
            "alpha_id": "Alpha008",
            "shared_assets": ["AU", "EURUSD"],
            "strategy_score": 0.7, "alpha_score": 0.97,
            "combined_score": 1.0, "status": "CANDIDATE",
            "next_step": "PAPER_TRADING",
        }]},
    }


def test_export_csv_writes_the_four_files(tmp_path):
    from research.discovery.factor.export_csv import export

    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(_minimal_report()), encoding="utf-8")
    out = tmp_path / "csv"
    counts = export(report_path, out)

    assert counts == {"pairs_all": 2, "pairs_gate_passed": 1,
                      "alpha_ranking": 2, "convergence": 1}

    rows = list(csv.DictReader((out / "pairs_gate_passed.csv").open()))
    assert len(rows) == 1
    r = rows[0]
    assert r["alpha_id"] == "Alpha008" and r["asset"] == "EURUSD"
    # check details are parsed to numbers (train / val / robustness / cost)
    assert float(r["train_ic"]) == pytest.approx(-0.4326)
    assert float(r["train_sharpe"]) == pytest.approx(23.26)
    assert float(r["val_ic"]) == pytest.approx(-0.4245)
    assert float(r["val_return"]) == pytest.approx(2.5431)
    assert float(r["oos_sharpe"]) == pytest.approx(26.6595)
    assert float(r["oos_return"]) == pytest.approx(13.136682)
    assert (r["wf_positive"], r["wf_total"]) == ("6", "6")
    assert float(r["wf_frac"]) == pytest.approx(1.0)
    assert float(r["stability_frac"]) == pytest.approx(1.0)
    assert float(r["one_way_bps"]) == pytest.approx(1.5)
    assert float(r["slippage_bps"]) == pytest.approx(0.5)
    assert r["is_final_candidate_alpha"] == "True"
    assert float(r["score"]) == pytest.approx(0.97)

    # rejects keep their fail reason and the per-check booleans
    all_rows = list(csv.DictReader((out / "pairs_all.csv").open()))
    rejected = next(r for r in all_rows if r["alpha_id"] == "Alpha009")
    assert rejected["passed"] == "False"
    assert rejected["fail_reason"] == "train_ic"
    assert rejected["check_train_ic"] == "False"
    assert rejected["check_dataset_gate"] == "True"
    assert rejected["is_final_candidate_alpha"] == "False"

    # convergence params are stored as JSON, assets joined with |
    conv = list(csv.DictReader((out / "convergence.csv").open()))
    assert json.loads(conv[0]["strategy_params"]) == {"fast": 9, "slow": 21}
    assert conv[0]["shared_assets"] == "AU|EURUSD"

    # alpha ranking carries the cross-asset summary
    alpha = list(csv.DictReader((out / "alpha_ranking.csv").open()))
    assert alpha[0]["alpha_id"] == "Alpha008"
    assert alpha[0]["status"] == "CANDIDATE"
    assert alpha[0]["assets_passed"] == "EURUSD"
