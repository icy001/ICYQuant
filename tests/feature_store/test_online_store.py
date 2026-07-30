"""测试 Online Feature Store — 在线特征存储。

覆盖: 写入、读取、更新、删除、过期、批量操作。
"""

import time

import pytest

from services.feature_store.online_store import OnlineFeatureStore, OnlineFeatureRecord, StoreTTL


class TestOnlineFeatureStoreSet:
    """写入操作测试。"""

    def test_set_single_entity(self):
        """设置单个实体特征应成功。"""
        store = OnlineFeatureStore()
        record = store.set("NVDA", {"ema20": 182.31, "atr14": 4.82})
        assert record.entity_id == "NVDA"
        assert record.features["ema20"] == 182.31
        assert record.features["atr14"] == 4.82

    def test_set_with_ttl(self):
        """带TTL写入应正确设置过期时间。"""
        store = OnlineFeatureStore()
        record = store.set("AAPL", {"rsi14": 65.5}, ttl=StoreTTL.REALTIME)
        assert record.ttl == StoreTTL.REALTIME
        assert record.expires_at > record.created_at

    def test_set_with_metadata(self):
        """带元数据写入应正确存储。"""
        store = OnlineFeatureStore()
        record = store.set("TSLA", {"volume": 1e6}, metadata={"source": "live"})
        assert record.metadata["source"] == "live"


class TestOnlineFeatureStoreGet:
    """读取操作测试。"""

    def test_get_existing(self):
        """读取存在的实体应返回特征。"""
        store = OnlineFeatureStore()
        store.set("NVDA", {"ema20": 182.31})
        features = store.get("NVDA")
        assert features is not None
        assert features["ema20"] == 182.31

    def test_get_not_found(self):
        """读取不存在的实体应返回 None。"""
        store = OnlineFeatureStore()
        assert store.get("NONEXISTENT") is None

    def test_get_single_feature(self):
        """读取单个特征应正确。"""
        store = OnlineFeatureStore()
        store.set("NVDA", {"ema20": 182.31, "atr14": 4.82})
        assert store.get_feature("NVDA", "ema20") == 182.31
        assert store.get_feature("NVDA", "atr14") == 4.82

    def test_get_feature_not_found(self):
        """读取不存在的特征应返回 None。"""
        store = OnlineFeatureStore()
        store.set("NVDA", {"ema20": 182.31})
        assert store.get_feature("NVDA", "nonexistent") is None
        assert store.get_feature("NONEXISTENT", "ema20") is None

    def test_batch_get(self):
        """批量读取应正确。"""
        store = OnlineFeatureStore()
        store.set("NVDA", {"ema20": 182.31})
        store.set("AAPL", {"ema20": 195.22})
        store.set("TSLA", {"ema20": 245.10})
        result = store.batch_get(["NVDA", "AAPL", "MISSING"])
        assert len(result) == 2
        assert result["NVDA"]["ema20"] == 182.31
        assert result["AAPL"]["ema20"] == 195.22
        assert "MISSING" not in result


class TestOnlineFeatureStoreUpdate:
    """更新操作测试。"""

    def test_update_existing(self):
        """更新存在的实体应合并特征。"""
        store = OnlineFeatureStore()
        store.set("NVDA", {"ema20": 182.31})
        record = store.update("NVDA", {"atr14": 4.82, "ema20": 183.00})
        assert record is not None
        features = store.get("NVDA")
        assert features["ema20"] == 183.00  # updated
        assert features["atr14"] == 4.82  # new

    def test_update_not_found(self):
        """更新不存在的实体应返回 None。"""
        store = OnlineFeatureStore()
        assert store.update("NONEXISTENT", {"ema20": 100.0}) is None


class TestOnlineFeatureStoreDelete:
    """删除操作测试。"""

    def test_delete_entity(self):
        """删除实体应成功。"""
        store = OnlineFeatureStore()
        store.set("NVDA", {"ema20": 182.31})
        assert store.delete("NVDA") is True
        assert store.get("NVDA") is None

    def test_delete_not_found(self):
        """删除不存在的实体应返回 False。"""
        store = OnlineFeatureStore()
        assert store.delete("NONEXISTENT") is False

    def test_delete_feature(self):
        """删除单个特征应成功。"""
        store = OnlineFeatureStore()
        store.set("NVDA", {"ema20": 182.31, "atr14": 4.82})
        assert store.delete_feature("NVDA", "ema20") is True
        assert store.get_feature("NVDA", "ema20") is None
        assert store.get_feature("NVDA", "atr14") == 4.82

    def test_delete_feature_not_found(self):
        """删除不存在的特征应返回 False。"""
        store = OnlineFeatureStore()
        store.set("NVDA", {"ema20": 182.31})
        assert store.delete_feature("NVDA", "nonexistent") is False


class TestOnlineFeatureStoreExpiry:
    """过期处理测试。"""

    def test_expired_record_returns_none(self):
        """过期记录应返回 None。"""
        store = OnlineFeatureStore()
        # Manually create an expired record
        record = OnlineFeatureRecord(
            entity_id="NVDA",
            features={"ema20": 182.31},
            ttl=StoreTTL.REALTIME,
            created_at=time.time() - 100,  # created 100s ago
            expires_at=time.time() - 50,    # expired 50s ago
        )
        store._store["NVDA"] = record
        assert store.get("NVDA") is None

    def test_expire_removes_stale(self):
        """expire 应删除过期记录。"""
        store = OnlineFeatureStore()
        store.set("NVDA", {"ema20": 182.31})
        # Manually expire
        store._store["NVDA"].expires_at = time.time() - 1
        count = store.expire()
        assert count == 1
        assert store.entity_count() == 0

    def test_clear(self):
        """clear 应清空所有数据。"""
        store = OnlineFeatureStore()
        store.set("NVDA", {"ema20": 182.31})
        store.set("AAPL", {"rsi14": 65.5})
        store.clear()
        assert store.entity_count() == 0


class TestOnlineFeatureStoreIndex:
    """特征索引测试。"""

    def test_get_entities_with_feature(self):
        """应按特征名查找实体列表。"""
        store = OnlineFeatureStore()
        store.set("NVDA", {"ema20": 182.31, "atr14": 4.82})
        store.set("AAPL", {"ema20": 195.22})
        entities = store.get_entities_with_feature("ema20")
        assert "NVDA" in entities
        assert "AAPL" in entities

    def test_index_updated_on_delete(self):
        """删除实体应更新索引。"""
        store = OnlineFeatureStore()
        store.set("NVDA", {"ema20": 182.31})
        store.delete("NVDA")
        assert "NVDA" not in store.get_entities_with_feature("ema20")


class TestOnlineFeatureStoreStats:
    """统计信息测试。"""

    def test_entity_count(self):
        """entity_count 应返回实体数。"""
        store = OnlineFeatureStore()
        assert store.entity_count() == 0
        store.set("NVDA", {"ema20": 182.31})
        store.set("AAPL", {"rsi14": 65.5})
        assert store.entity_count() == 2

    def test_feature_count(self):
        """feature_count 应返回唯一特征数。"""
        store = OnlineFeatureStore()
        store.set("NVDA", {"ema20": 182.31, "atr14": 4.82})
        store.set("AAPL", {"rsi14": 65.5})
        assert store.feature_count() == 3  # ema20, atr14, rsi14
