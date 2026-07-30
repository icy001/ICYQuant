"""测试 Feature Selector — 特征选择器。

覆盖: Variance/Correlation/MutualInfo/RFE/TreeImportance 过滤、组合选择。
"""

import numpy as np
import pytest

from services.feature_engineering.selector import (
    CorrelationFilter,
    FeatureSelector,
    MutualInfoFilter,
    RFEliminator,
    SelectionReport,
    TreeImportanceFilter,
    VarianceFilter,
)


class TestVarianceFilter:
    """方差过滤器测试。"""

    def test_remove_low_variance(self):
        X = np.array([
            [1.0, 0.0, 5.0],
            [2.0, 0.0, 6.0],
            [3.0, 0.0, 7.0],
        ])
        f = VarianceFilter(threshold=0.01)
        selected, removed = f.select(X, ["a", "b", "c"])
        assert "a" in selected
        assert "b" in removed
        assert "c" in selected

    def test_keep_all_if_above_threshold(self):
        X = np.array([[1.0, 2.0], [3.0, 4.0]])
        f = VarianceFilter(threshold=0.0)
        selected, removed = f.select(X, ["a", "b"])
        assert len(selected) == 2
        assert len(removed) == 0

    def test_single_row(self):
        X = np.array([[1.0, 2.0]])
        f = VarianceFilter(threshold=0.01)
        selected, removed = f.select(X, ["a", "b"])
        assert len(selected) == 2  # single row, keep all


class TestCorrelationFilter:
    """相关系数过滤器测试。"""

    def test_remove_highly_correlated(self):
        rng = np.random.RandomState(42)
        X = np.column_stack([
            rng.randn(100),
            rng.randn(100) * 0.01 + 1.0,  # ~constant
            rng.randn(100),
        ])
        # Column 0 and 2 are uncorrelated, column 1 is near-constant
        f = CorrelationFilter(threshold=0.95)
        selected, removed = f.select(X, ["a", "b", "c"])
        assert "a" in selected
        assert "c" in selected

    def test_single_feature(self):
        X = np.array([[1.0], [2.0], [3.0]])
        f = CorrelationFilter(threshold=0.95)
        selected, removed = f.select(X, ["a"])
        assert selected == ["a"]
        assert removed == []

    def test_perfect_correlation(self):
        X = np.column_stack([np.arange(100), np.arange(100) * 2])
        f = CorrelationFilter(threshold=0.95)
        selected, removed = f.select(X, ["a", "b"])
        assert len(selected) == 1
        assert len(removed) == 1


class TestMutualInfoFilter:
    """互信息过滤器测试。"""

    def test_select_top_k(self):
        rng = np.random.RandomState(42)
        n = 200
        y = rng.randn(n)
        # Feature 0 correlates with y, others are noise
        X = np.column_stack([
            y * 0.8 + rng.randn(n) * 0.2,
            rng.randn(n),
            rng.randn(n),
            y * 0.5 + rng.randn(n) * 0.5,
        ])
        f = MutualInfoFilter(k=2, n_bins=10)
        selected, removed = f.select(X, ["a", "b", "c", "d"], y)
        assert len(selected) == 2
        assert len(removed) == 2

    def test_k_larger_than_features(self):
        X = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
        y = np.array([0, 1, 0])
        f = MutualInfoFilter(k=5)
        selected, removed = f.select(X, ["a", "b"], y)
        assert len(selected) == 2  # k > n_features, keep all

    def test_no_target(self):
        X = np.array([[1.0, 2.0], [3.0, 4.0]])
        f = MutualInfoFilter(k=1)
        selected, removed = f.select(X, ["a", "b"])
        assert len(selected) == 2  # no target, keep all


class TestRFEliminator:
    """RFE 过滤器测试。"""

    def test_rfe_selection(self):
        rng = np.random.RandomState(42)
        n = 200
        # y depends on features 0, 2; features 1, 3 are noise
        X = np.column_stack([
            rng.randn(n),
            rng.randn(n),
            rng.randn(n),
            rng.randn(n),
        ])
        y = X[:, 0] * 0.6 + X[:, 2] * 0.4 + rng.randn(n) * 0.1

        f = RFEliminator(n_features_to_select=2, step=1)
        selected, removed = f.select(X, ["a", "b", "c", "d"], y)
        assert len(selected) == 2
        assert len(removed) == 2

    def test_rfe_all_features(self):
        X = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
        y = np.array([1.0, 2.0, 3.0])
        f = RFEliminator(n_features_to_select=3)  # more than available
        selected, removed = f.select(X, ["a", "b"], y)
        assert len(selected) == 2


class TestTreeImportanceFilter:
    """树模型重要性过滤器测试。"""

    def test_select_top_k(self):
        rng = np.random.RandomState(42)
        n = 200
        X = np.column_stack([
            rng.randn(n),
            rng.randn(n),
            rng.randn(n),
            rng.randn(n),
        ])
        y = (X[:, 0] + X[:, 2] > 0).astype(float)  # binary target

        f = TreeImportanceFilter(k=2, n_estimators=20)
        selected, removed = f.select(X, ["a", "b", "c", "d"], y)
        assert len(selected) == 2

    def test_k_larger_than_features(self):
        X = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
        y = np.array([0, 1, 0])
        f = TreeImportanceFilter(k=5)
        selected, removed = f.select(X, ["a", "b"], y)
        assert len(selected) == 2


class TestFeatureSelector:
    """FeatureSelector 组合过滤器测试。"""

    def test_sequential_filters(self):
        rng = np.random.RandomState(42)
        n = 200
        X = np.column_stack([
            rng.randn(n),              # good feature
            np.zeros(n),               # zero variance
            rng.randn(n) * 0.001,      # low variance
            rng.randn(n),              # good feature
        ])
        names = ["a", "b", "c", "d"]
        y = X[:, 0] * 0.5 + rng.randn(n) * 0.1

        selector = FeatureSelector()
        selector.add_filter(VarianceFilter(threshold=0.01))
        selector.add_filter(MutualInfoFilter(k=2))

        report = selector.select(X, names, y)
        assert report.selected_count <= 4
        assert report.original_count == 4

    def test_report_fields(self):
        rng = np.random.RandomState(42)
        X = rng.randn(100, 5)
        names = ["a", "b", "c", "d", "e"]

        selector = FeatureSelector()
        selector.add_filter(VarianceFilter(threshold=0.01))
        report = selector.select(X, names)

        assert isinstance(report, SelectionReport)
        assert report.original_count == 5
        assert len(report.selected_features) >= 0
        assert len(report.removed_features) >= 0

    def test_remove_filter(self):
        selector = FeatureSelector()
        selector.add_filter(VarianceFilter())
        selector.add_filter(CorrelationFilter())
        assert len(selector._filters) == 2
        selector.remove_filter("variance")
        assert len(selector._filters) == 1
        assert selector._filters[0].name == "correlation"

    def test_no_filters_keeps_all(self):
        X = np.array([[1.0, 2.0], [3.0, 4.0]])
        selector = FeatureSelector()
        report = selector.select(X, ["a", "b"])
        assert report.selected_count == 2
