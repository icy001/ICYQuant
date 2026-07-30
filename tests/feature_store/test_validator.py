"""测试 Feature Validator — 特征数据校验。

覆盖: 缺失值、类型检查、异常值、值范围、重复时间戳、时间连续性、前瞻偏差。
"""

import pytest

from services.feature_store.validator import (
    FeatureValidator,
    ValidationReport,
    ValidationRule,
    Severity,
)


class TestValidationReport:
    """ValidationReport 测试。"""

    def test_passed_by_default(self):
        """默认情况下 passed 应为 True。"""
        report = ValidationReport(feature_name="ema20")
        assert report.passed is True

    def test_errors_warnings_info(self):
        """errors/warnings/info 应正确分类。"""
        from services.feature_store.validator import ValidationIssue

        report = ValidationReport(feature_name="test")
        report.add_issue(ValidationIssue(rule=ValidationRule.MISSING_VALUES, severity=Severity.ERROR, message="e1"))
        report.add_issue(ValidationIssue(rule=ValidationRule.OUTLIER_DETECTION, severity=Severity.WARNING, message="w1"))
        report.add_issue(ValidationIssue(rule=ValidationRule.TYPE_CHECK, severity=Severity.INFO, message="i1"))

        assert len(report.errors) == 1
        assert len(report.warnings) == 1
        assert len(report.info) == 1


class TestMissingValues:
    """缺失值检查测试。"""

    def test_no_missing(self):
        """无缺失值应通过。"""
        validator = FeatureValidator(max_missing_ratio=0.05)
        report = validator.validate("ema20", [1.0, 2.0, 3.0, 4.0, 5.0])
        assert report.passed is True

    def test_missing_below_threshold(self):
        """缺失值低于阈值应只产生 warning。"""
        validator = FeatureValidator(max_missing_ratio=0.2)
        report = validator.validate("ema20", [1.0, None, 3.0, 4.0, 5.0])
        assert report.passed is True
        assert any(i.rule == ValidationRule.MISSING_VALUES and i.severity == Severity.WARNING for i in report.issues)

    def test_missing_above_threshold(self):
        """缺失值超过阈值应不通过。"""
        validator = FeatureValidator(max_missing_ratio=0.1)
        report = validator.validate("ema20", [1.0, None, None, 4.0, None])
        assert report.passed is False
        assert any(i.severity == Severity.ERROR for i in report.issues)

    def test_empty_values(self):
        """空值列表应不通过。"""
        validator = FeatureValidator()
        report = validator.validate("ema20", [])
        assert report.passed is False

    def test_nan_values(self):
        """NaN 值应被视为缺失。"""
        validator = FeatureValidator(max_missing_ratio=0.2)
        report = validator.validate("ema20", [1.0, float("nan"), 3.0, 4.0, 5.0])
        assert report.passed is True
        assert any(i.rule == ValidationRule.MISSING_VALUES for i in report.issues)


class TestTypeCheck:
    """类型检查测试。"""

    def test_all_correct_type(self):
        """全部正确类型应通过。"""
        validator = FeatureValidator()
        report = validator.validate("ema20", [1.0, 2.0, 3.0], expected_dtype=float)
        assert report.passed is True

    def test_type_mismatch(self):
        """类型不匹配应不通过。"""
        validator = FeatureValidator()
        report = validator.validate("ema20", [1.0, "bad", 3.0], expected_dtype=float)
        assert report.passed is False
        assert any(i.rule == ValidationRule.TYPE_CHECK and i.severity == Severity.ERROR for i in report.issues)


class TestOutlierDetection:
    """异常值检测测试。"""

    def test_no_outliers(self):
        """无异常值应通过。"""
        validator = FeatureValidator(outlier_std_threshold=3.0)
        report = validator.validate("ema20", [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        assert report.passed is True

    def test_outlier_detected(self):
        """有异常值应产生 warning。"""
        validator = FeatureValidator(outlier_std_threshold=2.0)
        report = validator.validate("ema20", [1.0, 2.0, 3.0, 4.0, 5.0, 100.0])
        assert any(i.rule == ValidationRule.OUTLIER_DETECTION for i in report.issues)

    def test_insufficient_data(self):
        """数据不足时不应报异常值。"""
        validator = FeatureValidator()
        report = validator.validate("ema20", [1.0, 2.0])
        assert not any(i.rule == ValidationRule.OUTLIER_DETECTION for i in report.issues)


class TestValueRange:
    """值范围检查测试。"""

    def test_within_range(self):
        """值在范围内应通过。"""
        validator = FeatureValidator(min_value=0.0, max_value=100.0)
        report = validator.validate("ema20", [10.0, 20.0, 50.0])
        assert report.passed is True

    def test_out_of_range(self):
        """值超出范围应不通过。"""
        validator = FeatureValidator(min_value=0.0, max_value=100.0)
        report = validator.validate("ema20", [10.0, 200.0, 50.0])
        assert report.passed is False
        assert any(i.rule == ValidationRule.VALUE_RANGE for i in report.issues)

    def test_no_range_constraints(self):
        """无范围限制应通过。"""
        validator = FeatureValidator()  # no min/max
        report = validator.validate("ema20", [10.0, 99999.0])
        assert report.passed is True


class TestDuplicateTimestamps:
    """重复时间戳测试。"""

    def test_no_duplicates(self):
        """无重复应通过。"""
        validator = FeatureValidator()
        report = validator.validate("ema20", [1.0, 2.0, 3.0], timestamps=[100.0, 200.0, 300.0])
        assert report.passed is True

    def test_duplicates(self):
        """有重复应不通过。"""
        validator = FeatureValidator()
        report = validator.validate("ema20", [1.0, 2.0, 3.0], timestamps=[100.0, 100.0, 300.0])
        assert report.passed is False
        assert any(i.rule == ValidationRule.DUPLICATE_INDEX for i in report.issues)


class TestTemporalContinuity:
    """时间连续性测试。"""

    def test_sorted_timestamps(self):
        """排序的时间戳应通过。"""
        validator = FeatureValidator(
            enabled_rules=[ValidationRule.TEMPORAL_CONTINUITY],
        )
        report = validator.validate("ema20", [1.0, 2.0, 3.0], timestamps=[100.0, 200.0, 300.0])
        assert report.passed is True

    def test_unsorted_timestamps(self):
        """未排序的时间戳应产生 warning。"""
        validator = FeatureValidator(
            enabled_rules=[ValidationRule.TEMPORAL_CONTINUITY],
        )
        report = validator.validate("ema20", [1.0, 2.0, 3.0], timestamps=[300.0, 100.0, 200.0])
        assert any(i.rule == ValidationRule.TEMPORAL_CONTINUITY for i in report.issues)


class TestLookaheadBias:
    """前瞻偏差测试。"""

    def test_no_lookahead(self):
        """无前瞻偏差应通过。"""
        validator = FeatureValidator()
        report = validator.validate(
            "ema20",
            [1.0, 2.0, 3.0],
            timestamps=[100.0, 200.0, 300.0],
            reference_timestamps=[50.0, 150.0, 250.0, 350.0],
        )
        assert report.passed is True

    def test_lookahead_detected(self):
        """有前瞻偏差应不通过。"""
        validator = FeatureValidator()
        report = validator.validate(
            "ema20",
            [1.0, 2.0, 3.0],
            timestamps=[100.0, 200.0, 500.0],  # 500 > max reference (350)
            reference_timestamps=[50.0, 150.0, 250.0],
        )
        assert report.passed is False
        assert any(i.rule == ValidationRule.LOOKAHEAD_BIAS for i in report.issues)

    def test_no_timestamps_skip(self):
        """无时间戳应跳过时序检查。"""
        validator = FeatureValidator()
        report = validator.validate("ema20", [1.0, 2.0, 3.0])
        assert report.passed is True


class TestValidatorConfiguration:
    """校验器配置测试。"""

    def test_custom_rules(self):
        """自定义规则集应生效。"""
        validator = FeatureValidator(
            enabled_rules=[ValidationRule.MISSING_VALUES],
            max_missing_ratio=0.0,
        )
        # Only missing values check should run; even with outliers, no outlier rule
        report = validator.validate("ema20", [1.0, 2.0, 3.0, 4.0, 5.0, 100.0])
        assert not any(i.rule == ValidationRule.OUTLIER_DETECTION for i in report.issues)

    def test_summary_statistics(self):
        """报告摘要应包含正确统计。"""
        validator = FeatureValidator(max_missing_ratio=0.0)
        report = validator.validate("ema20", [1.0, None, 3.0])
        assert report.summary["total_values"] == 3
        assert report.summary["error_count"] >= 1
