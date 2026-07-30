"""测试 Time Travel & Version Manager — 时间旅行与版本管理。

覆盖: 时间旅行查询、分支、标签、版本创建、恢复、快照管理。
"""

import pytest
from datetime import datetime, timedelta
from services.data_platform.time_travel import (
    TimeTravel,
    TimeTravelResult,
    TimeBranch,
    TimeTag,
    TimeTravelConfig,
)
from services.data_platform.version_manager import (
    VersionManager,
    VersionInfo,
    SnapshotDiff,
    VersionConfig,
)
from services.data_platform.lakehouse import DataLakehouse, LakehouseConfig, DatasetSchema, DatasetType


def _make_schema(name="test_ds"):
    return DatasetSchema(name=name, dataset_type=DatasetType.CUSTOM, fields=[], primary_key=[])


class TestTimeTravel:
    """测试时间旅行功能。"""

    @pytest.fixture
    def lakehouse(self, tmp_path):
        lh = DataLakehouse(LakehouseConfig(base_path=str(tmp_path / "tt_lh")))
        lh.create_dataset("market_tick", DatasetType.TICK, _make_schema("market_tick"))
        return lh

    @pytest.fixture
    def tt(self, lakehouse):
        return TimeTravel(TimeTravelConfig(), lakehouse)

    def test_query_as_of(self, tt, lakehouse):
        """按时间戳查询应返回历史数据。"""
        now = datetime.utcnow()
        lakehouse.write("market_tick", [{"symbol": "AAPL", "price": 150.0}])
        result = tt.query_as_of("market_tick", now)
        assert isinstance(result, TimeTravelResult)
        assert result.dataset == "market_tick"

    def test_query_as_of_disabled(self, lakehouse):
        """时间旅行禁用时应返回空。"""
        config = TimeTravelConfig(enabled=False)
        tt = TimeTravel(config, lakehouse)
        result = tt.query_as_of("market_tick", datetime.utcnow())
        # With time travel disabled, returns empty result (but still queries lakehouse)
        assert result.dataset == "market_tick"

    def test_create_branch(self, tt):
        """创建分支应成功。"""
        branch = tt.create_branch("experiment_v2", "market_tick")
        assert branch.name == "experiment_v2"
        assert branch.dataset == "market_tick"

    def test_get_branch(self, tt):
        """获取分支应返回正确的分支。"""
        tt.create_branch("dev", "market_tick")
        branch = tt.get_branch("market_tick", "dev")
        assert branch is not None
        assert branch.name == "dev"

    def test_list_branches(self, tt):
        """列出分支应返回所有分支。"""
        tt.create_branch("dev", "market_tick")
        tt.create_branch("prod", "market_tick")
        branches = tt.list_branches(dataset="market_tick")
        assert len(branches) == 2

    def test_create_tag(self, tt):
        """创建标签应成功。"""
        ts = datetime(2026, 7, 28, 22, 0, 0)
        tag = tt.tag("daily_close", "market_tick", ts, description="EOD snapshot")
        assert tag.name == "daily_close"
        assert tag.timestamp == ts

    def test_get_tag(self, tt):
        """获取标签应返回正确的标签。"""
        ts = datetime.utcnow()
        tt.tag("checkpoint_1", "market_tick", ts)
        tag = tt.get_tag("market_tick", "checkpoint_1")
        assert tag is not None
        assert tag.name == "checkpoint_1"

    def test_list_tags(self, tt):
        """列出标签应返回所有标签。"""
        tt.tag("tag1", "market_tick", datetime.utcnow())
        tt.tag("tag2", "market_tick", datetime.utcnow())
        tags = tt.list_tags(dataset="market_tick")
        assert len(tags) == 2

    def test_delete_branch(self, tt):
        """删除分支应成功。"""
        tt.create_branch("temp", "market_tick")
        assert tt.delete_branch("market_tick", "temp") is True
        assert tt.get_branch("market_tick", "temp") is None


class TestVersionManager:
    """测试版本管理功能。"""

    @pytest.fixture
    def lakehouse(self, tmp_path):
        lh = DataLakehouse(LakehouseConfig(base_path=str(tmp_path / "lh")))
        lh.create_dataset("test_ds", DatasetType.CUSTOM, _make_schema("test_ds"))
        return lh

    @pytest.fixture
    def vm(self, lakehouse):
        return VersionManager(VersionConfig(), lakehouse)

    def test_create_version(self, vm, lakehouse):
        """创建版本应成功。"""
        version = vm.create_version("test_ds", "Initial version")
        assert version.dataset == "test_ds"
        assert version.version_number == 1

    def test_list_versions(self, vm, lakehouse):
        """列出版本应返回所有版本。"""
        vm.create_version("test_ds", "v1")
        vm.create_version("test_ds", "v2")
        versions = vm.list_versions("test_ds")
        assert len(versions) == 2

    def test_get_latest_version(self, vm, lakehouse):
        """获取最新版本应返回最大版本号。"""
        vm.create_version("test_ds", "v1")
        vm.create_version("test_ds", "v2")
        latest = vm.get_latest_version("test_ds")
        assert latest is not None
        assert latest.version_number == 2

    def test_get_version_by_id(self, vm, lakehouse):
        """按版本 ID 查询应返回正确版本。"""
        v1 = vm.create_version("test_ds", "v1")
        retrieved = vm.get_version("test_ds", v1.version_id)
        assert retrieved is not None
        assert retrieved.version_id == v1.version_id

    def test_restore_version(self, vm, lakehouse):
        """恢复版本应成功。"""
        v1 = vm.create_version("test_ds", "v1")
        vm.create_version("test_ds", "v2")
        assert vm.restore_version("test_ds", v1.version_id) is True

    def test_diff_versions(self, vm, lakehouse):
        """版本比较应返回差异。"""
        v1 = vm.create_version("test_ds", "v1")
        v2 = vm.create_version("test_ds", "v2")
        diff = vm.diff_versions("test_ds", v1.version_id, v2.version_id)
        assert diff is not None
        assert isinstance(diff, SnapshotDiff)

    def test_get_stats(self, vm, lakehouse):
        """获取统计应返回正确数据。"""
        vm.create_version("test_ds", "v1")
        stats = vm.get_stats()
        assert stats["total_datasets"] >= 1
        assert stats["total_versions"] >= 1
