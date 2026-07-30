"""测试 Metadata Catalog — 元数据目录。

覆盖: 注册、查询、搜索、标签索引、统计。
"""

import pytest
from services.data_platform.metadata_catalog import (
    MetadataCatalog,
    CatalogEntry,
    CatalogEntryType,
    SearchResult,
)
from services.data_platform.config import DataClassification, CatalogConfig


class TestMetadataCatalogRegister:
    """测试元数据注册。"""

    @pytest.fixture
    def catalog(self):
        return MetadataCatalog(CatalogConfig())

    def test_register_entry(self, catalog):
        """注册条目应成功并返回 CatalogEntry。"""
        entry = CatalogEntry(
            name="market_tick",
            entry_type=CatalogEntryType.DATASET,
            owner="market_team",
            description="Market tick data",
        )
        result = catalog.register("market_tick", entry)
        assert result.name == "market_tick"
        assert result.owner == "market_team"
        assert result.entry_type == CatalogEntryType.DATASET

    def test_register_duplicate_raises(self, catalog):
        """重复注册应抛出 ValueError。"""
        entry = CatalogEntry(name="test", entry_type=CatalogEntryType.DATASET)
        catalog.register("test", entry)
        with pytest.raises(ValueError):
            catalog.register("test", entry)

    def test_update_entry(self, catalog):
        """更新条目应修改字段。"""
        entry = CatalogEntry(name="test", entry_type=CatalogEntryType.DATASET)
        catalog.register("test", entry)
        updated = catalog.update("test", owner="new_owner", description="updated")
        assert updated is not None
        assert updated.owner == "new_owner"
        assert updated.description == "updated"

    def test_deregister_entry(self, catalog):
        """注销条目应移除。"""
        entry = CatalogEntry(name="test", entry_type=CatalogEntryType.DATASET)
        catalog.register("test", entry)
        assert catalog.deregister("test") is True
        assert catalog.get("test") is None

    def test_deregister_nonexistent(self, catalog):
        """注销不存在的条目应返回 False。"""
        assert catalog.deregister("nonexistent") is False


class TestMetadataCatalogLookup:
    """测试元数据查询。"""

    @pytest.fixture
    def catalog(self):
        cat = MetadataCatalog(CatalogConfig())
        for i, ds_type in enumerate([CatalogEntryType.DATASET, CatalogEntryType.FEATURE, CatalogEntryType.MODEL]):
            entry = CatalogEntry(
                name=f"entry_{i}",
                entry_type=ds_type,
                owner=f"team_{i % 2}",
                tags=[f"tag_{i}"],
            )
            cat.register(f"entry_{i}", entry)
        return cat

    def test_get_by_name(self, catalog):
        """按名称查询应返回正确的条目。"""
        entry = catalog.get("entry_0")
        assert entry is not None
        assert entry.entry_type == CatalogEntryType.DATASET

    def test_list_by_type(self, catalog):
        """按类型过滤应返回正确数量的条目。"""
        datasets = catalog.list_all(entry_type=CatalogEntryType.DATASET)
        assert len(datasets) == 1

    def test_list_by_owner(self, catalog):
        """按 owner 过滤应返回正确数量。"""
        owned = catalog.list_all(owner="team_0")
        assert len(owned) >= 1

    def test_list_by_classification(self, catalog):
        """按分类过滤应返回正确数量。"""
        entries = catalog.list_all(classification=DataClassification.INTERNAL)
        assert len(entries) == 3


class TestMetadataCatalogSearch:
    """测试元数据搜索。"""

    @pytest.fixture
    def catalog(self):
        cat = MetadataCatalog(CatalogConfig())
        entries = [
            CatalogEntry(name="market_tick", entry_type=CatalogEntryType.DATASET,
                         owner="market_team", description="Real-time market tick data",
                         tags=["market", "tick", "real-time"]),
            CatalogEntry(name="market_bar", entry_type=CatalogEntryType.DATASET,
                         owner="market_team", description="OHLCV bar data",
                         tags=["market", "bar"]),
            CatalogEntry(name="momentum_feature", entry_type=CatalogEntryType.FEATURE,
                         owner="feature_team", description="Momentum indicator",
                         tags=["feature", "momentum"]),
        ]
        for e in entries:
            cat.register(e.name, e)
        return cat

    def test_search_by_name(self, catalog):
        """按名称搜索应找到匹配条目。"""
        result = catalog.search("tick")
        assert result.total_matches >= 1
        assert any(e.name == "market_tick" for e in result.entries)

    def test_search_by_description(self, catalog):
        """按描述搜索应找到匹配条目。"""
        result = catalog.search("momentum")
        assert result.total_matches >= 1

    def test_search_by_tag(self, catalog):
        """按标签搜索应找到匹配条目。"""
        result = catalog.search("market")
        assert result.total_matches >= 2

    def test_search_with_type_filter(self, catalog):
        """按类型过滤搜索应限制结果。"""
        result = catalog.search("market", entry_type=CatalogEntryType.FEATURE)
        assert all(e.entry_type == CatalogEntryType.FEATURE for e in result.entries)

    def test_search_no_match(self, catalog):
        """无匹配搜索应返回空结果。"""
        result = catalog.search("nonexistent_xyz")
        assert result.total_matches == 0


class TestMetadataCatalogStats:
    """测试元数据统计。"""

    def test_get_catalog_stats(self):
        """获取目录统计应返回正确计数。"""
        catalog = MetadataCatalog(CatalogConfig())
        for i in range(5):
            entry = CatalogEntry(
                name=f"entry_{i}",
                entry_type=CatalogEntryType.DATASET,
                owner="team_a",
            )
            catalog.register(f"entry_{i}", entry)

        stats = catalog.get_catalog_stats()
        assert stats["total_entries"] == 5
        assert stats["by_type"]["dataset"] == 5
        assert stats["by_owner"]["team_a"] == 5

    def test_get_by_tag(self, catalog=None):
        """按标签查询应返回正确条目。"""
        cat = MetadataCatalog(CatalogConfig())
        entry = CatalogEntry(
            name="test", entry_type=CatalogEntryType.DATASET, tags=["alpha", "beta"]
        )
        cat.register("test", entry)
        assert len(cat.get_by_tag("alpha")) == 1
        assert len(cat.get_by_tag("gamma")) == 0
