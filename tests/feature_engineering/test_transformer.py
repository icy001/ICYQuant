"""测试 Feature Transformer — 特征变换器。

覆盖: Normalize/Standardize/Log/Rank/Clip/Winsorize 变换及拟合。
"""

import math

import numpy as np
import pytest

from services.feature_engineering.transformer import (
    ClipTransformer,
    LogTransformer,
    NormalizeTransformer,
    RankTransformer,
    StandardizeTransformer,
    TransformContext,
    TransformResult,
    WinsorizeTransformer,
)


class TestNormalizeTransformer:
    """Min-Max 归一化测试。"""

    def test_basic_normalize(self):
        t = NormalizeTransformer()
        result = t.fit_transform([0.0, 5.0, 10.0])
        assert result.values == pytest.approx([0.0, 0.5, 1.0])

    def test_custom_range(self):
        t = NormalizeTransformer(feature_range=(-1.0, 1.0))
        result = t.fit_transform([0.0, 5.0, 10.0])
        assert result.values == pytest.approx([-1.0, 0.0, 1.0])

    def test_single_value(self):
        t = NormalizeTransformer()
        result = t.fit_transform([5.0, 5.0, 5.0])
        # Scale = 0, all values = range min
        assert result.values == [0.0, 0.0, 0.0]

    def test_with_nan(self):
        t = NormalizeTransformer()
        result = t.fit_transform([0.0, float("nan"), 10.0])
        assert result.values[0] == 0.0
        assert math.isnan(result.values[1])
        assert result.values[2] == 1.0

    def test_inverse_transform(self):
        t = NormalizeTransformer()
        ctx = t.fit([0.0, 10.0])
        original = t.inverse_transform([0.0, 0.5, 1.0], ctx)
        assert original == pytest.approx([0.0, 5.0, 10.0])

    def test_clip_option(self):
        t = NormalizeTransformer(clip=False)
        result = t.fit_transform([0.0, 5.0, 10.0])
        assert result.values == pytest.approx([0.0, 0.5, 1.0])

    def test_empty_input(self):
        t = NormalizeTransformer()
        result = t.fit_transform([])
        assert result.values == []


class TestStandardizeTransformer:
    """Z-score 标准化测试。"""

    def test_basic_standardize(self):
        t = StandardizeTransformer()
        result = t.fit_transform([1.0, 2.0, 3.0, 4.0, 5.0])
        mean = np.mean(result.values)
        std = np.std(result.values, ddof=0)
        assert mean == pytest.approx(0.0, abs=1e-9)
        assert std == pytest.approx(1.0, abs=1e-9)

    def test_with_nan(self):
        t = StandardizeTransformer()
        result = t.fit_transform([1.0, float("nan"), 3.0, 4.0, 5.0])
        assert math.isnan(result.values[1])
        assert not math.isnan(result.values[0])

    def test_inverse_transform(self):
        t = StandardizeTransformer()
        original = [1.0, 2.0, 3.0, 4.0, 5.0]
        ctx = t.fit(original)
        transformed = t.transform(original, ctx)
        restored = t.inverse_transform(transformed.values, ctx)
        assert restored == pytest.approx(original)

    def test_no_mean_option(self):
        t = StandardizeTransformer(with_mean=False, with_std=False)
        result = t.fit_transform([1.0, 2.0, 3.0])
        assert result.values == pytest.approx([1.0, 2.0, 3.0])

    def test_zero_std(self):
        t = StandardizeTransformer()
        result = t.fit_transform([5.0, 5.0, 5.0])
        assert result.values == [0.0, 0.0, 0.0]
        assert "std is zero" in result.warnings[0]


class TestLogTransformer:
    """对数变换测试。"""

    def test_natural_log(self):
        t = LogTransformer(offset=0.0)
        result = t.fit_transform([1.0, math.e, math.e ** 2])
        assert result.values == pytest.approx([0.0, 1.0, 2.0])

    def test_with_offset(self):
        t = LogTransformer(offset=1.0)
        result = t.fit_transform([0.0, math.e - 1])
        assert result.values[0] == pytest.approx(0.0)
        assert result.values[1] == pytest.approx(1.0)

    def test_negative_with_offset(self):
        t = LogTransformer(offset=5.0)
        result = t.fit_transform([-4.0, -3.0])
        assert not any(math.isnan(v) for v in result.values)

    def test_base10(self):
        t = LogTransformer(base=10.0, offset=0.0)
        result = t.fit_transform([1.0, 10.0, 100.0])
        assert result.values == pytest.approx([0.0, 1.0, 2.0])

    def test_inverse_transform(self):
        t = LogTransformer(offset=1.0)
        ctx = t.fit([0.0, math.e - 1])
        restored = t.inverse_transform([0.0, 1.0], ctx)
        assert restored[0] == pytest.approx(0.0)
        assert restored[1] == pytest.approx(math.e - 1)


class TestRankTransformer:
    """Rank 变换测试。"""

    def test_rank_normalized(self):
        t = RankTransformer(normalize=True)
        result = t.fit_transform([10.0, 30.0, 20.0])
        assert result.values[0] == pytest.approx(1.0 / 3)
        assert result.values[1] == pytest.approx(1.0)
        assert result.values[2] == pytest.approx(2.0 / 3)

    def test_rank_not_normalized(self):
        t = RankTransformer(normalize=False)
        result = t.fit_transform([10.0, 30.0, 20.0])
        assert result.values == [1.0, 3.0, 2.0]

    def test_rank_with_nan(self):
        t = RankTransformer()
        result = t.fit_transform([10.0, float("nan"), 20.0, float("nan")])
        assert math.isnan(result.values[1])
        assert math.isnan(result.values[3])

    def test_all_nan(self):
        t = RankTransformer()
        result = t.fit_transform([float("nan"), float("nan")])
        assert all(math.isnan(v) for v in result.values)

    def test_ties_average(self):
        t = RankTransformer(method="average", normalize=False)
        result = t.fit_transform([5.0, 10.0, 10.0, 20.0])
        assert result.values[1] == result.values[2]
        assert result.values[1] == 2.5


class TestClipTransformer:
    """Clip 变换测试。"""

    def test_clip_both(self):
        t = ClipTransformer(lower=0.0, upper=10.0)
        result = t.fit_transform([-5.0, 5.0, 15.0])
        assert result.values == [0.0, 5.0, 10.0]

    def test_clip_lower_only(self):
        t = ClipTransformer(lower=0.0)
        result = t.fit_transform([-5.0, 5.0, 15.0])
        assert result.values == [0.0, 5.0, 15.0]

    def test_clip_upper_only(self):
        t = ClipTransformer(upper=10.0)
        result = t.fit_transform([-5.0, 5.0, 15.0])
        assert result.values == [-5.0, 5.0, 10.0]

    def test_no_clip(self):
        t = ClipTransformer()
        result = t.fit_transform([-5.0, 5.0, 15.0])
        assert result.values == [-5.0, 5.0, 15.0]

    def test_with_nan(self):
        t = ClipTransformer(lower=0.0)
        result = t.fit_transform([-5.0, float("nan"), 15.0])
        assert math.isnan(result.values[1])


class TestWinsorizeTransformer:
    """Winsorize 变换测试。"""

    def test_winsorize_default(self):
        t = WinsorizeTransformer(limits=(0.25, 0.25))
        result = t.fit_transform([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
        # 25th percentile ~ 2.75, 75th ~ 6.25
        assert result.values[0] >= 2.0
        assert result.values[-1] <= 7.0

    def test_winsorize_no_clip_needed(self):
        t = WinsorizeTransformer(limits=(0.0, 0.0))
        result = t.fit_transform([1.0, 2.0, 3.0])
        assert result.values == [1.0, 2.0, 3.0]

    def test_empty(self):
        t = WinsorizeTransformer()
        result = t.fit_transform([])
        assert result.values == []


class TestTransformContext:
    """TransformContext 测试。"""

    def test_context_creation(self):
        ctx = TransformContext(params={"mean": 0.0, "std": 1.0})
        assert ctx.params["mean"] == 0.0

    def test_context_fit_values(self):
        ctx = TransformContext(fit_values=[1.0, 2.0, 3.0])
        assert ctx.fit_values == [1.0, 2.0, 3.0]


class TestTransformResult:
    """TransformResult 测试。"""

    def test_result_creation(self):
        r = TransformResult(values=[1.0, 2.0], params={"method": "zscore"})
        assert len(r.values) == 2
        assert r.params["method"] == "zscore"

    def test_result_warnings(self):
        r = TransformResult(values=[0.0], warnings=["std is zero"])
        assert len(r.warnings) == 1
