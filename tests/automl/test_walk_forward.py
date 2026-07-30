"""测试 Walk-Forward Validator & Time-Series CV。

覆盖: 窗口生成、训练/测试分割、稳定性评分、
扩展窗口 CV、指标聚合。
"""

import numpy as np
import pytest

from services.automl.walk_forward import (
    WalkForwardConfig,
    WalkForwardResult,
    WalkForwardValidator,
    WindowResult,
)
from services.automl.cross_validation import (
    CVConfig,
    CVResult,
    TimeSeriesCV,
)


# =================================================================
# Walk-Forward Validator
# =================================================================


class TestWalkForwardWindowGeneration:
    def test_no_windows_too_small(self):
        cfg = WalkForwardConfig(train_window=100, test_window=50, step_size=25, min_train_size=50)
        validator = WalkForwardValidator(cfg)
        windows = validator.generate_windows(80)  # < 100+50
        assert windows == []

    def test_single_window(self):
        cfg = WalkForwardConfig(train_window=100, test_window=50, step_size=100, anchored=True, min_train_size=100)
        validator = WalkForwardValidator(cfg)
        windows = validator.generate_windows(150)
        assert len(windows) == 1
        w = windows[0]
        assert w.train_start == 0
        assert w.train_end == 100
        assert w.test_start == 100
        assert w.test_end == 150

    def test_anchored_expanding(self):
        """Anchored: training window expands, test window slides."""
        cfg = WalkForwardConfig(
            train_window=100, test_window=50, step_size=50,
            anchored=True, min_train_size=50,
        )
        validator = WalkForwardValidator(cfg)
        windows = validator.generate_windows(250)
        assert len(windows) >= 2
        # First window
        assert windows[0].train_start == 0
        assert windows[0].train_end == 100
        assert windows[0].test_start == 100
        assert windows[0].test_end == 150
        # Second window: anchored -> training expands
        assert windows[1].train_start == 0
        assert windows[1].train_end == 150  # expanded
        assert windows[1].test_start == 150
        assert windows[1].test_end == 200

    def test_rolling_windows(self):
        """Rolling: both train and test slide forward."""
        cfg = WalkForwardConfig(
            train_window=100, test_window=50, step_size=50,
            anchored=False, min_train_size=100,
        )
        validator = WalkForwardValidator(cfg)
        windows = validator.generate_windows(250)
        assert len(windows) >= 2
        # First
        assert windows[0].train_start == 0
        assert windows[0].train_end == 100
        assert windows[0].test_start == 100
        assert windows[0].test_end == 150
        # Second: rolling -> train also slides
        assert windows[1].train_start == 50
        assert windows[1].train_end == 150
        assert windows[1].test_start == 150
        assert windows[1].test_end == 200

    def test_gap_between_train_test(self):
        cfg = WalkForwardConfig(
            train_window=100, test_window=50, anchored=True, gap=10, min_train_size=100,
        )
        validator = WalkForwardValidator(cfg)
        windows = validator.generate_windows(160)
        assert len(windows) == 1
        assert windows[0].train_end == 100
        assert windows[0].test_start == 110  # 100 + 10 gap

    def test_window_count(self):
        cfg = WalkForwardConfig(train_window=100, test_window=50, anchored=True, min_train_size=100)
        validator = WalkForwardValidator(cfg)
        assert validator.window_count(150) == 1
        assert validator.window_count(80) == 0


class TestWalkForwardRun:
    @pytest.fixture
    def returns(self):
        rng = np.random.RandomState(42)
        # 500 days with slight positive drift
        return (rng.randn(500) * 0.01 + 0.0005).tolist()

    @pytest.fixture
    def validator(self):
        cfg = WalkForwardConfig(
            train_window=200, test_window=63, step_size=63,
            anchored=True, min_train_size=100,
        )
        return WalkForwardValidator(cfg)

    def test_run_simple(self, validator, returns):
        """Simplified walk-forward with just returns."""

        def sharpe_eval(r: list) -> dict:
            arr = np.array(r)
            if len(arr) < 2 or np.std(arr) == 0:
                return {"sharpe": 0.0}
            return {"sharpe": float(np.mean(arr) / np.std(arr) * np.sqrt(252))}

        result = validator.run_simple(returns, sharpe_eval)
        assert result.n_windows >= 1
        assert "sharpe" in result.aggregate_test_metrics
        assert result.elapsed_seconds >= 0

    def test_run_with_train_and_eval(self, validator, returns):
        def train_fn(data):
            return {"mean": float(np.mean(data)), "len": len(data)}

        def eval_fn(item, model_info):
            return {"sharpe": abs(model_info["mean"] / 0.01)}

        result = validator.run(returns, train_fn, eval_fn)
        assert result.n_windows >= 1
        assert len(result.window_results) == result.n_windows

    def test_run_empty_data(self):
        validator = WalkForwardValidator()
        result = validator.run_simple([], lambda r: {"sharpe": 0})
        assert result.n_windows == 0
        assert result.window_results == []

    def test_stability_score(self, validator, returns):
        def eval_fn(r):
            arr = np.array(r)
            return {"sharpe": float(np.mean(arr) / (np.std(arr) or 1) * np.sqrt(252))}

        result = validator.run_simple(returns, eval_fn)
        assert 0.0 <= result.stability_score <= 1.0

    def test_is_robust(self, validator, returns):
        def eval_fn(r):
            arr = np.array(r)
            return {"sharpe": float(np.mean(arr) / (np.std(arr) or 1) * np.sqrt(252))}

        result = validator.run_simple(returns, eval_fn)
        assert isinstance(result.is_robust, bool)


class TestWalkForwardStability:
    def test_perfect_stability(self):
        assert WalkForwardValidator._compute_stability([1.0, 1.0, 1.0]) == 1.0

    def test_high_variability(self):
        vals = [0.5, 2.0, -0.5]
        stab = WalkForwardValidator._compute_stability(vals)
        assert stab < 0.8

    def test_single_value(self):
        assert WalkForwardValidator._compute_stability([5.0]) == 0.0

    def test_zero_mean(self):
        assert WalkForwardValidator._compute_stability([0.0, 0.0, 0.0]) == 0.0


# =================================================================
# Time-Series Cross Validation
# =================================================================


class TestTimeSeriesCV:

    def test_split_generation(self):
        cv = TimeSeriesCV(CVConfig(n_splits=3, test_size=50, min_train_size=100))
        splits = cv.split(300)  # 100 + 50*3 = 250 < 300
        assert len(splits) == 3
        for tr_s, tr_e, te_s, te_e in splits:
            assert tr_s == 0  # expanding from start
            assert te_s >= tr_e  # test after train
            assert te_e > te_s

    def test_split_insufficient_data(self):
        cv = TimeSeriesCV(CVConfig(n_splits=5, test_size=50, min_train_size=100))
        splits = cv.split(150)  # too small
        assert splits == []

    def test_n_splits(self):
        cv = TimeSeriesCV(CVConfig(n_splits=3, test_size=30, min_train_size=100))
        count = cv.n_splits(300)
        assert count == 3

    def test_split_ordering(self):
        """Each split's train_end must be before its test_start."""
        cv = TimeSeriesCV(CVConfig(n_splits=4, test_size=50, min_train_size=100))
        splits = cv.split(400)
        for tr_s, tr_e, te_s, te_e in splits:
            assert tr_e <= te_s  # no overlap

    def test_run_basic(self):
        cv = TimeSeriesCV(CVConfig(n_splits=3, test_size=30, min_train_size=100))
        rng = np.random.RandomState(42)
        returns = (rng.randn(300) * 0.01 + 0.0005).tolist()
        result = cv.run(returns)
        assert result.total_splits == 3
        assert "train_sharpe" in result.mean_metrics
        assert "test_sharpe" in result.mean_metrics
        assert len(result.fold_results) == 3

    def test_run_with_predictions(self):
        cv = TimeSeriesCV(CVConfig(n_splits=3, test_size=30, min_train_size=100))
        rng = np.random.RandomState(42)
        n = 300
        returns = rng.randn(n).tolist()
        preds = rng.randn(n).tolist()
        targets = returns  # same as returns for testing
        result = cv.run(returns, preds, targets)
        assert result.total_splits == 3

    def test_cv_result_has_std(self):
        cv = TimeSeriesCV(CVConfig(n_splits=4, test_size=30, min_train_size=100))
        rng = np.random.RandomState(42)
        returns = (rng.randn(250) * 0.01 + 0.0005).tolist()
        result = cv.run(returns)
        assert len(result.std_metrics) > 0
        assert result.elapsed_seconds > 0

    def test_absolute_test_size(self):
        cv = TimeSeriesCV(CVConfig(n_splits=3, test_size=30, min_train_size=50))
        # Absolute test_size (int)
        splits = cv.split(200)
        for _, _, te_s, te_e in splits:
            assert te_e - te_s == 30
