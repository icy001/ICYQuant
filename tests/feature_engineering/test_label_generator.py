"""测试 Label Generator — 标签生成器。

覆盖: 回归标签、二分类/多分类标签、排序标签、交叉截面排序。
"""

import math

import numpy as np
import pytest

from services.feature_engineering.label_generator import (
    ClassificationLabelGenerator,
    LabelConfig,
    LabelType,
    RankingLabelGenerator,
    RegressionLabelGenerator,
)


class TestLabelConfig:
    """LabelConfig 数据类测试。"""

    def test_default_config(self):
        cfg = LabelConfig()
        assert cfg.horizon == 5
        assert cfg.target_col == "close"
        assert cfg.threshold == 0.0
        assert cfg.bins == 3

    def test_custom_config(self):
        cfg = LabelConfig(horizon=10, target_col="vwap", threshold=0.005, bins=5)
        assert cfg.horizon == 10
        assert cfg.target_col == "vwap"
        assert cfg.threshold == 0.005
        assert cfg.bins == 5


class TestRegressionLabelGenerator:
    """回归标签生成器测试。"""

    def test_basic_generation(self):
        gen = RegressionLabelGenerator(LabelConfig(horizon=2))
        prices = [100.0, 101.0, 102.0, 103.0, 104.0]
        result = gen.generate(prices)
        assert len(result.labels) == 5
        # label[0] = (102-100)/100 = 0.02
        assert result.labels[0] == pytest.approx(0.02)
        # label[3] = nan (no future data)
        assert math.isnan(result.labels[3])
        assert math.isnan(result.labels[4])

    def test_zero_price(self):
        gen = RegressionLabelGenerator(LabelConfig(horizon=1))
        result = gen.generate([0.0, 100.0, 200.0])
        assert math.isnan(result.labels[0])

    def test_metadata(self):
        gen = RegressionLabelGenerator(LabelConfig(horizon=5))
        result = gen.generate([100.0] * 20)
        assert result.label_type == LabelType.REGRESSION
        assert result.metadata["horizon"] == 5

    def test_smoothing(self):
        cfg = LabelConfig(horizon=2, smoothing=True, smoothing_alpha=0.5)
        gen = RegressionLabelGenerator(cfg)
        prices = [100.0, 102.0, 100.0, 104.0, 106.0]
        result = gen.generate(prices)
        assert len(result.labels) == 5


class TestClassificationLabelGenerator:
    """分类标签生成器测试。"""

    def test_binary_labels(self):
        cfg = LabelConfig(horizon=1, threshold=0.01)
        gen = ClassificationLabelGenerator(cfg, num_classes=2)
        prices = [100.0, 102.0, 101.0, 98.0, 105.0]
        result = gen.generate(prices)
        assert result.label_type == LabelType.BINARY_CLASSIFICATION
        # price goes 100->102 (+2%), label=1 (up)
        assert result.labels[0] == 1.0
        # price goes 102->101 (-0.98%), within ±1% → nan (flat)
        assert math.isnan(result.labels[1])
        # price goes 101->98 (-2.97%), below -1% → label=0 (down)
        assert result.labels[2] == 0.0
        # price goes 98->105 (+7.14%), above +1% → label=1 (up)
        assert result.labels[3] == 1.0

    def test_binary_nan_for_flat(self):
        cfg = LabelConfig(horizon=1, threshold=0.05)  # 5% threshold
        gen = ClassificationLabelGenerator(cfg, num_classes=2)
        prices = [100.0, 101.0, 102.0]
        result = gen.generate(prices)
        # 100->101 = 1%, below threshold -> nan
        assert math.isnan(result.labels[0])

    def test_multiclass_labels(self):
        cfg = LabelConfig(horizon=1, bins=3)
        gen = ClassificationLabelGenerator(cfg, num_classes=3)
        # Generate data with clear up/down/flat
        prices = [100.0, 110.0, 105.0, 95.0, 100.0, 108.0]
        result = gen.generate(prices)
        assert result.label_type == LabelType.MULTICLASS_CLASSIFICATION

    def test_insufficient_data_multiclass(self):
        cfg = LabelConfig(horizon=1, bins=5)
        gen = ClassificationLabelGenerator(cfg, num_classes=5)
        prices = [100.0, 101.0, 102.0]
        result = gen.generate(prices)
        assert "insufficient data" in result.metadata.get("error", "")


class TestRankingLabelGenerator:
    """排序标签生成器测试。"""

    def test_basic_ranking(self):
        gen = RankingLabelGenerator(LabelConfig(horizon=2))
        prices = [100.0, 101.0, 102.0, 103.0, 104.0]
        result = gen.generate(prices)
        assert result.label_type == LabelType.RANKING
        # Ranks should be in [0, 1]
        valid = [v for v in result.labels if not math.isnan(v)]
        assert all(0.0 <= v <= 1.0 for v in valid)

    def test_ranking_order(self):
        gen = RankingLabelGenerator(LabelConfig(horizon=1))
        prices = [100.0, 110.0, 105.0, 95.0]
        result = gen.generate(prices)
        valid = [(i, v) for i, v in enumerate(result.labels) if not math.isnan(v)]
        # Highest forward return (100->110=10%) gets highest rank
        assert len(valid) == 3

    def test_cross_sectional_ranking(self):
        gen = RankingLabelGenerator(LabelConfig(horizon=2))
        # 3 symbols, 5 time steps
        values_matrix = [
            [100.0, 101.0, 102.0, 103.0, 104.0],
            [200.0, 202.0, 204.0, 206.0, 208.0],
            [50.0, 51.0, 52.0, 53.0, 54.0],
        ]
        results = gen.generate_cross_sectional(values_matrix)
        assert len(results) == 3
        for r in results:
            assert r.label_type == LabelType.RANKING

    def test_insufficient_data_ranking(self):
        gen = RankingLabelGenerator(LabelConfig(horizon=1))
        result = gen.generate([100.0, 101.0])
        assert "insufficient data" in result.metadata.get("error", "")


class TestEdgeCases:
    """边界情况测试。"""

    def test_empty_input(self):
        gen = RegressionLabelGenerator(LabelConfig(horizon=1))
        result = gen.generate([])
        assert result.labels == []

    def test_single_value(self):
        gen = RegressionLabelGenerator(LabelConfig(horizon=1))
        result = gen.generate([100.0])
        assert len(result.labels) == 1
        assert math.isnan(result.labels[0])

    def test_all_same_price(self):
        gen = RegressionLabelGenerator(LabelConfig(horizon=3))
        result = gen.generate([100.0] * 10)
        valid = [v for v in result.labels if not math.isnan(v)]
        assert all(v == pytest.approx(0.0) for v in valid)

    def test_nan_in_input(self):
        gen = RegressionLabelGenerator(LabelConfig(horizon=2))
        prices = [100.0, float("nan"), 102.0, 103.0, 104.0]
        result = gen.generate(prices)
        assert len(result.labels) == 5
