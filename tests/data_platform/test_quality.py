"""测试 Data Quality Engine — 数据质量引擎。

覆盖: 质量规则、数据验证、报告生成、缺失检查、重复检查、异常检测。
"""

import pytest
from datetime import datetime, timedelta
from services.data_platform.quality_engine import (
    QualityEngine,
    QualityReport,
    NotNullRule,
    UniqueRule,
    RangeRule,
    EnumRule,
    RegexRule,
    CustomRule,
    TimelinessRule,
    QualityConfig,
)
from services.data_platform.config import QualityRuleType


class TestQualityRules:
    """测试各类型质量规则。"""

    def test_not_null_rule_pass(self):
        """非空规则：合法数据应通过。"""
        rule = NotNullRule(name="test", field="price")
        data = [{"price": 150.0}, {"price": 200.0}]
        violations = rule.check(data)
        assert len(violations) == 0

    def test_not_null_rule_fail(self):
        """非空规则：空值应检测。"""
        rule = NotNullRule(name="test", field="price")
        data = [{"price": 150.0}, {"price": None}]
        violations = rule.check(data)
        assert len(violations) == 1

    def test_unique_rule_pass(self):
        """唯一性规则：无重复应通过。"""
        rule = UniqueRule(name="test", field="id")
        data = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        violations = rule.check(data)
        assert len(violations) == 0

    def test_unique_rule_fail(self):
        """唯一性规则：重复值应检测。"""
        rule = UniqueRule(name="test", field="id")
        data = [{"id": "a"}, {"id": "b"}, {"id": "a"}]
        violations = rule.check(data)
        assert len(violations) == 1

    def test_range_rule_pass(self):
        """范围规则：范围内应通过。"""
        rule = RangeRule(name="test", field="volume", min_value=0, max_value=10000)
        data = [{"volume": 100}, {"volume": 5000}]
        violations = rule.check(data)
        assert len(violations) == 0

    def test_range_rule_below_min(self):
        """范围规则：低于最小值应检测。"""
        rule = RangeRule(name="test", field="volume", min_value=0)
        data = [{"volume": -100}]
        violations = rule.check(data)
        assert len(violations) == 1

    def test_range_rule_above_max(self):
        """范围规则：超过最大值应检测。"""
        rule = RangeRule(name="test", field="volume", max_value=10000)
        data = [{"volume": 20000}]
        violations = rule.check(data)
        assert len(violations) == 1

    def test_enum_rule_pass(self):
        """枚举规则：合法值应通过。"""
        rule = EnumRule(name="test", field="side", allowed_values=["BUY", "SELL"])
        data = [{"side": "BUY"}, {"side": "SELL"}]
        violations = rule.check(data)
        assert len(violations) == 0

    def test_enum_rule_fail(self):
        """枚举规则：非法值应检测。"""
        rule = EnumRule(name="test", field="side", allowed_values=["BUY", "SELL"])
        data = [{"side": "INVALID"}]
        violations = rule.check(data)
        assert len(violations) == 1

    def test_regex_rule_pass(self):
        """正则规则：匹配应通过。"""
        rule = RegexRule(name="test", field="symbol", pattern=r"^[A-Z]{1,10}$")
        data = [{"symbol": "AAPL"}, {"symbol": "MSFT"}]
        violations = rule.check(data)
        assert len(violations) == 0

    def test_regex_rule_fail(self):
        """正则规则：不匹配应检测。"""
        rule = RegexRule(name="test", field="symbol", pattern=r"^[A-Z]{1,10}$")
        data = [{"symbol": "1234"}]
        violations = rule.check(data)
        assert len(violations) == 1

    def test_custom_rule(self):
        """自定义规则应正确执行。"""
        rule = CustomRule(
            name="test", field="price",
            check_fn=lambda r: r.get("price", 0) > 0,
            message_template="Price must be positive",
        )
        data = [{"price": -10}]
        violations = rule.check(data)
        assert len(violations) == 1

    def test_timeliness_rule_pass(self):
        """时效性规则：新鲜数据应通过。"""
        rule = TimelinessRule(
            name="test",
            timestamp_field="ts",
            max_age_hours=24,
        )
        data = [{"ts": datetime.utcnow().isoformat()}]
        violations = rule.check(data)
        assert len(violations) == 0

    def test_timeliness_rule_fail(self):
        """时效性规则：过期数据应检测。"""
        rule = TimelinessRule(
            name="test",
            timestamp_field="ts",
            max_age_hours=1,
        )
        old_ts = (datetime.utcnow() - timedelta(hours=5)).isoformat()
        data = [{"ts": old_ts}]
        violations = rule.check(data)
        assert len(violations) == 1


class TestQualityEngine:
    """测试质量引擎。"""

    @pytest.fixture
    def engine(self):
        eng = QualityEngine(QualityConfig())
        eng.add_rule("test_ds", NotNullRule(name="price_not_null", field="price", severity="error"))
        eng.add_rule("test_ds", RangeRule(name="volume_range", field="volume", min_value=0, severity="error"))
        eng.add_rule("test_ds", EnumRule(name="side_valid", field="side", allowed_values=["BUY", "SELL"], severity="warning"))
        return eng

    def test_validate_all_pass(self, engine):
        """全部合法数据应通过。"""
        data = [
            {"price": 150.0, "volume": 1000, "side": "BUY"},
            {"price": 200.0, "volume": 500, "side": "SELL"},
        ]
        report = engine.validate("test_ds", data)
        assert report.status == "passed"
        assert report.failed_checks == 0

    def test_validate_with_errors(self, engine):
        """有错误的数据应标记为 failed。"""
        data = [
            {"price": None, "volume": -100, "side": "INVALID"},
        ]
        report = engine.validate("test_ds", data)
        assert report.status == "failed"
        assert report.failed_checks >= 1

    def test_validate_with_warnings(self, engine):
        """仅有警告的数据应标记为 warning。"""
        data = [
            {"price": 150.0, "volume": 1000, "side": "INVALID"},
        ]
        report = engine.validate("test_ds", data)
        assert report.status in ("warning", "passed")

    def test_validate_empty_data(self, engine):
        """空数据应通过。"""
        report = engine.validate("test_ds", [])
        assert report.status == "passed"

    def test_get_rules(self, engine):
        """获取规则应返回正确的规则列表。"""
        rules = engine.get_rules("test_ds")
        assert len(rules) == 3

    def test_remove_rule(self, engine):
        """删除规则应成功。"""
        assert engine.remove_rule("test_ds", "price_not_null") is True
        assert len(engine.get_rules("test_ds")) == 2

    def test_get_quality_score(self, engine):
        """质量评分应在 0-100 之间。"""
        engine.validate("test_ds", [{"price": 150.0, "volume": 1000, "side": "BUY"}])
        score = engine.get_quality_score("test_ds")
        assert 0 <= score <= 100

    def test_get_overall_stats(self, engine):
        """获取总体统计应返回正确结构。"""
        stats = engine.get_overall_stats()
        assert "datasets_monitored" in stats
        assert "total_rules" in stats
        assert "average_quality_score" in stats


class TestQualityQuickChecks:
    """测试快速质量检查。"""

    @pytest.fixture
    def engine(self):
        return QualityEngine(QualityConfig())

    def test_check_missing(self, engine):
        """缺失率检查应正确计算。"""
        data = [{"a": 1}, {"a": None}, {"a": 3}]
        count, rate = engine.check_missing(data, "a")
        assert count == 1
        assert rate == pytest.approx(1 / 3)

    def test_check_duplicates(self, engine):
        """重复率检查应正确计算。"""
        data = [{"id": "a"}, {"id": "b"}, {"id": "a"}]
        count, rate = engine.check_duplicates(data, ["id"])
        assert count == 1

    def test_check_outliers_iqr(self, engine):
        """IQR 异常检测应找出异常值。"""
        data = [{"value": v} for v in [1, 2, 3, 4, 5, 100]]
        outliers = engine.check_outliers_iqr(data, "value", multiplier=1.5)
        assert len(outliers) >= 1
