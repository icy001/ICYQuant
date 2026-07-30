"""测试 Feature Versioning — 特征版本管理。

覆盖: 版本创建、晋升、回滚、diff、历史查询。
"""

import pytest

from services.feature_store.versioning import FeatureVersioning, FeatureVersion, VersionStage


class TestFeatureVersionCreation:
    """版本创建测试。"""

    def test_create_version(self):
        """创建版本应成功。"""
        versioning = FeatureVersioning()
        fv = versioning.create("ema20", "v1", {"window": 20})
        assert fv.feature_name == "ema20"
        assert fv.version == "v1"
        assert fv.definition == {"window": 20}
        assert fv.stage == VersionStage.EXPERIMENTAL

    def test_create_duplicate_version_fails(self):
        """重复版本应抛出异常。"""
        versioning = FeatureVersioning()
        versioning.create("ema20", "v1")
        with pytest.raises(ValueError, match="already exists"):
            versioning.create("ema20", "v1")

    def test_create_with_parent(self):
        """带父版本创建应正确。"""
        versioning = FeatureVersioning()
        fv = versioning.create("ema20", "v2", parent_version="v1", changelog="Changed window to 30")
        assert fv.parent_version == "v1"
        assert fv.changelog == "Changed window to 30"

    def test_create_multiple_features(self):
        """多特征多版本创建应正确。"""
        versioning = FeatureVersioning()
        versioning.create("ema20", "v1")
        versioning.create("ema20", "v2")
        versioning.create("rsi14", "v1")
        assert len(versioning.list_history("ema20")) == 2
        assert len(versioning.list_history("rsi14")) == 1


class TestFeatureVersionPromotion:
    """版本晋升测试。"""

    def test_promote_to_active(self):
        """晋升到 ACTIVE 应成功。"""
        versioning = FeatureVersioning()
        versioning.create("ema20", "v1")
        fv = versioning.promote("ema20", "v1", VersionStage.ACTIVE)
        assert fv.stage == VersionStage.ACTIVE

    def test_promote_chain(self):
        """链式晋升应正确。"""
        versioning = FeatureVersioning()
        versioning.create("ema20", "v1")
        fv = versioning.promote("ema20", "v1", VersionStage.VALIDATED)
        assert fv.stage == VersionStage.VALIDATED
        fv = versioning.promote("ema20", "v1", VersionStage.ACTIVE)
        assert fv.stage == VersionStage.ACTIVE

    def test_promote_supersedes_previous(self):
        """晋升新版本应自动废弃旧版本。"""
        versioning = FeatureVersioning()
        versioning.create("ema20", "v1")
        versioning.create("ema20", "v2")
        versioning.promote("ema20", "v1", VersionStage.ACTIVE)
        versioning.promote("ema20", "v2", VersionStage.ACTIVE)

        v1 = versioning.get("ema20", "v1")
        assert v1.stage == VersionStage.SUPERSEDED
        v2 = versioning.get("ema20", "v2")
        assert v2.stage == VersionStage.ACTIVE

    def test_promote_not_found(self):
        """晋升不存在的版本应抛出异常。"""
        versioning = FeatureVersioning()
        with pytest.raises(KeyError):
            versioning.promote("ema20", "v1", VersionStage.ACTIVE)


class TestFeatureVersionRollback:
    """版本回滚测试。"""

    def test_rollback(self):
        """回滚应恢复到上一个 ACTIVE 版本。"""
        versioning = FeatureVersioning()
        versioning.create("ema20", "v1")
        versioning.create("ema20", "v2")
        versioning.promote("ema20", "v1", VersionStage.ACTIVE)
        versioning.promote("ema20", "v2", VersionStage.ACTIVE)

        rolled = versioning.rollback("ema20")
        assert rolled is not None
        assert rolled.version == "v1"
        assert rolled.stage == VersionStage.ACTIVE

    def test_rollback_no_superseded(self):
        """无 SUPERSEDED 版本时回滚应返回 None。"""
        versioning = FeatureVersioning()
        versioning.create("ema20", "v1")
        versioning.promote("ema20", "v1", VersionStage.ACTIVE)
        assert versioning.rollback("ema20") is None

    def test_rollback_not_found(self):
        """回滚不存在特征应返回 None。"""
        versioning = FeatureVersioning()
        assert versioning.rollback("nonexistent") is None


class TestFeatureVersionQuery:
    """版本查询测试。"""

    def test_get_active(self):
        """获取活跃版本应正确。"""
        versioning = FeatureVersioning()
        versioning.create("ema20", "v1")
        versioning.promote("ema20", "v1", VersionStage.ACTIVE)
        active = versioning.get_active("ema20")
        assert active is not None
        assert active.version == "v1"

    def test_get_active_not_found(self):
        """无活跃版本应返回 None。"""
        versioning = FeatureVersioning()
        versioning.create("ema20", "v1")
        assert versioning.get_active("ema20") is None

    def test_list_history(self):
        """历史列表应按时间排序。"""
        versioning = FeatureVersioning()
        versioning.create("ema20", "v1")
        versioning.create("ema20", "v2")
        versioning.create("ema20", "v3")
        history = versioning.list_history("ema20")
        assert len(history) == 3

    def test_list_history_empty(self):
        """空历史应返回空列表。"""
        versioning = FeatureVersioning()
        assert versioning.list_history("nonexistent") == []


class TestFeatureVersionDiff:
    """版本 diff 测试。"""

    def test_diff_added(self):
        """diff 应检测新增字段。"""
        versioning = FeatureVersioning()
        versioning.create("ema20", "v1", {"window": 20})
        versioning.create("ema20", "v2", {"window": 20, "method": "exponential"})
        diff = versioning.diff("ema20", "v1", "v2")
        assert diff["added"] == {"method": "exponential"}
        assert diff["removed"] == {}
        assert diff["changed"] == {}

    def test_diff_removed(self):
        """diff 应检测删除字段。"""
        versioning = FeatureVersioning()
        versioning.create("ema20", "v1", {"window": 20, "method": "simple"})
        versioning.create("ema20", "v2", {"window": 20})
        diff = versioning.diff("ema20", "v1", "v2")
        assert diff["removed"] == {"method": "simple"}
        assert diff["added"] == {}

    def test_diff_changed(self):
        """diff 应检测修改字段。"""
        versioning = FeatureVersioning()
        versioning.create("ema20", "v1", {"window": 20})
        versioning.create("ema20", "v2", {"window": 30})
        diff = versioning.diff("ema20", "v1", "v2")
        assert diff["changed"] == {"window": {"from": 20, "to": 30}}

    def test_diff_not_found(self):
        """diff 不存在版本应抛出异常。"""
        versioning = FeatureVersioning()
        versioning.create("ema20", "v1", {"window": 20})
        with pytest.raises(KeyError):
            versioning.diff("ema20", "v1", "v99")


class TestFeatureVersionRetire:
    """版本退休测试。"""

    def test_retire_through_promote(self):
        """通过晋升到 RETIRED 状态。"""
        versioning = FeatureVersioning()
        versioning.create("ema20", "v1")
        versioning.promote("ema20", "v1", VersionStage.RETIRED)
        fv = versioning.get("ema20", "v1")
        assert fv.stage == VersionStage.RETIRED
