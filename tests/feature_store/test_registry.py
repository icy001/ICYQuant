"""测试 Feature Registry — 特征注册中心。

覆盖: 注册、查询、搜索、版本管理、状态变更。
"""

import pytest

from services.feature_store.registry import FeatureDefinition, FeatureRegistry, FeatureStatus


class TestFeatureDefinition:
    """FeatureDefinition 数据类测试。"""

    def test_create_definition(self):
        """创建特征定义应正确设置字段。"""
        fd = FeatureDefinition(
            feature_name="ema20",
            version="v1",
            owner="research",
            dtype="float64",
            frequency="1d",
            description="20-period EMA",
        )
        assert fd.feature_name == "ema20"
        assert fd.version == "v1"
        assert fd.owner == "research"
        assert fd.dtype == "float64"
        assert fd.frequency == "1d"
        assert fd.description == "20-period EMA"
        assert fd.status == FeatureStatus.DRAFT

    def test_default_values(self):
        """默认值应正确。"""
        fd = FeatureDefinition(feature_name="rsi14")
        assert fd.version == "v1"
        assert fd.owner == "research"
        assert fd.dtype == "float64"
        assert fd.frequency == "1d"
        assert fd.status == FeatureStatus.DRAFT
        assert fd.tags == []
        assert fd.metadata == {}
        assert fd.registered_at > 0

    def test_tags(self):
        """标签应正确存储。"""
        fd = FeatureDefinition(
            feature_name="macd",
            tags=["momentum", "trend"],
        )
        assert "momentum" in fd.tags
        assert "trend" in fd.tags

    def test_category(self):
        """分类应正确存储。"""
        fd = FeatureDefinition(feature_name="atr14", category="volatility")
        assert fd.category == "volatility"


class TestFeatureRegistryRegister:
    """注册操作测试。"""

    def test_register_single(self):
        """注册单个特征应成功。"""
        registry = FeatureRegistry()
        fd = FeatureDefinition(feature_name="ema20", version="v1")
        result = registry.register(fd)
        assert result.feature_name == "ema20"
        assert result.status == FeatureStatus.REGISTERED

    def test_register_duplicate_fails(self):
        """重复注册同名同版本应抛出异常。"""
        registry = FeatureRegistry()
        registry.register(FeatureDefinition(feature_name="ema20", version="v1"))
        with pytest.raises(ValueError, match="already registered"):
            registry.register(FeatureDefinition(feature_name="ema20", version="v1"))

    def test_register_different_versions(self):
        """同一特征不同版本应可注册。"""
        registry = FeatureRegistry()
        registry.register(FeatureDefinition(feature_name="ema20", version="v1"))
        registry.register(FeatureDefinition(feature_name="ema20", version="v2"))
        versions = registry.list_versions("ema20")
        assert len(versions) == 2

    def test_register_multiple_features(self):
        """注册多个不同特征应成功。"""
        registry = FeatureRegistry()
        registry.register(FeatureDefinition(feature_name="ema20", version="v1"))
        registry.register(FeatureDefinition(feature_name="rsi14", version="v1"))
        registry.register(FeatureDefinition(feature_name="macd", version="v1"))
        assert registry.count() == 3
        assert len(registry.feature_names()) == 3


class TestFeatureRegistryGet:
    """查询操作测试。"""

    def test_get_by_name_version(self):
        """按名称和版本查询应正确。"""
        registry = FeatureRegistry()
        registry.register(FeatureDefinition(feature_name="ema20", version="v1"))
        fd = registry.get("ema20", "v1")
        assert fd.feature_name == "ema20"
        assert fd.version == "v1"

    def test_get_latest(self):
        """不指定版本应返回最新注册的。"""
        registry = FeatureRegistry()
        registry.register(FeatureDefinition(feature_name="ema20", version="v1"))
        registry.register(FeatureDefinition(feature_name="ema20", version="v2"))
        fd = registry.get("ema20")
        assert fd.version == "v2"

    def test_get_not_found(self):
        """查询不存在的特征应抛出异常。"""
        registry = FeatureRegistry()
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_get_version_not_found(self):
        """查询不存在的版本应抛出异常。"""
        registry = FeatureRegistry()
        registry.register(FeatureDefinition(feature_name="ema20", version="v1"))
        with pytest.raises(KeyError):
            registry.get("ema20", "v99")


class TestFeatureRegistryList:
    """列表查询测试。"""

    def test_list_versions(self):
        """list_versions 应返回所有版本。"""
        registry = FeatureRegistry()
        registry.register(FeatureDefinition(feature_name="ema20", version="v1"))
        registry.register(FeatureDefinition(feature_name="ema20", version="v2"))
        registry.register(FeatureDefinition(feature_name="ema20", version="v3"))
        versions = registry.list_versions("ema20")
        assert len(versions) == 3

    def test_list_all(self):
        """list_all 应返回所有特征。"""
        registry = FeatureRegistry()
        registry.register(FeatureDefinition(feature_name="ema20", version="v1"))
        registry.register(FeatureDefinition(feature_name="rsi14", version="v1"))
        all_features = registry.list_all()
        assert len(all_features) == 2
        assert "ema20" in all_features
        assert "rsi14" in all_features

    def test_list_active(self):
        """list_active 只应返回 REGISTERED 状态的特征。"""
        registry = FeatureRegistry()
        registry.register(FeatureDefinition(feature_name="ema20", version="v1"))
        registry.register(FeatureDefinition(feature_name="rsi14", version="v1"))
        registry.deprecate("rsi14", "v1")
        active = registry.list_active()
        assert len(active) == 1
        assert active[0].feature_name == "ema20"

    def test_list_versions_not_found(self):
        """查询不存在特征的版本列表应抛出异常。"""
        registry = FeatureRegistry()
        with pytest.raises(KeyError):
            registry.list_versions("nonexistent")


class TestFeatureRegistrySearch:
    """搜索测试。"""

    def test_search_by_category(self):
        """按分类搜索应正确过滤。"""
        registry = FeatureRegistry()
        registry.register(FeatureDefinition(feature_name="ema20", version="v1", category="price"))
        registry.register(FeatureDefinition(feature_name="rsi14", version="v1", category="momentum"))
        results = registry.search(category="price")
        assert len(results) == 1
        assert results[0].feature_name == "ema20"

    def test_search_by_owner(self):
        """按负责人搜索应正确过滤。"""
        registry = FeatureRegistry()
        registry.register(FeatureDefinition(feature_name="ema20", version="v1", owner="alice"))
        registry.register(FeatureDefinition(feature_name="rsi14", version="v1", owner="bob"))
        results = registry.search(owner="alice")
        assert len(results) == 1
        assert results[0].feature_name == "ema20"

    def test_search_by_tag(self):
        """按标签搜索应正确过滤。"""
        registry = FeatureRegistry()
        registry.register(FeatureDefinition(feature_name="ema20", version="v1", tags=["trend"]))
        registry.register(FeatureDefinition(feature_name="rsi14", version="v1", tags=["momentum"]))
        results = registry.search(tag="trend")
        assert len(results) == 1
        assert results[0].feature_name == "ema20"

    def test_search_by_dtype(self):
        """按数据类型搜索应正确过滤。"""
        registry = FeatureRegistry()
        registry.register(FeatureDefinition(feature_name="ema20", version="v1", dtype="float64"))
        registry.register(FeatureDefinition(feature_name="flag", version="v1", dtype="bool"))
        results = registry.search(dtype="bool")
        assert len(results) == 1
        assert results[0].feature_name == "flag"

    def test_search_by_status(self):
        """按状态搜索应正确过滤。"""
        registry = FeatureRegistry()
        registry.register(FeatureDefinition(feature_name="ema20", version="v1"))
        registry.register(FeatureDefinition(feature_name="rsi14", version="v1"))
        registry.deprecate("rsi14", "v1")
        results = registry.search(status=FeatureStatus.DEPRECATED)
        assert len(results) == 1

    def test_search_no_results(self):
        """无匹配时应返回空列表。"""
        registry = FeatureRegistry()
        results = registry.search(category="nonexistent")
        assert results == []


class TestFeatureRegistryLifecycle:
    """特征生命周期测试。"""

    def test_deprecate(self):
        """废弃特征应更新状态。"""
        registry = FeatureRegistry()
        registry.register(FeatureDefinition(feature_name="ema20", version="v1"))
        fd = registry.deprecate("ema20", "v1")
        assert fd.status == FeatureStatus.DEPRECATED

    def test_retire(self):
        """退休特征应更新状态。"""
        registry = FeatureRegistry()
        registry.register(FeatureDefinition(feature_name="ema20", version="v1"))
        fd = registry.retire("ema20", "v1")
        assert fd.status == FeatureStatus.RETIRED

    def test_deprecate_not_found(self):
        """废弃不存在特征应抛出异常。"""
        registry = FeatureRegistry()
        with pytest.raises(KeyError):
            registry.deprecate("nonexistent", "v1")

    def test_update(self):
        """更新特征字段应成功。"""
        registry = FeatureRegistry()
        registry.register(FeatureDefinition(feature_name="ema20", version="v1"))
        fd = registry.update("ema20", "v1", description="Updated description", dtype="float32")
        assert fd.description == "Updated description"
        assert fd.dtype == "float32"

    def test_exists(self):
        """exists 检查应正确。"""
        registry = FeatureRegistry()
        registry.register(FeatureDefinition(feature_name="ema20", version="v1"))
        assert registry.exists("ema20", "v1") is True
        assert registry.exists("ema20", "v99") is False
        assert registry.exists("nonexistent", "v1") is False


class TestFeatureRegistryCount:
    """计数统计测试。"""

    def test_count(self):
        """count 应返回总版本数。"""
        registry = FeatureRegistry()
        assert registry.count() == 0
        registry.register(FeatureDefinition(feature_name="ema20", version="v1"))
        registry.register(FeatureDefinition(feature_name="ema20", version="v2"))
        registry.register(FeatureDefinition(feature_name="rsi14", version="v1"))
        assert registry.count() == 3

    def test_feature_names(self):
        """feature_names 应返回排序后的特征名。"""
        registry = FeatureRegistry()
        registry.register(FeatureDefinition(feature_name="ccc", version="v1"))
        registry.register(FeatureDefinition(feature_name="aaa", version="v1"))
        registry.register(FeatureDefinition(feature_name="bbb", version="v1"))
        names = registry.feature_names()
        assert names == ["aaa", "bbb", "ccc"]
