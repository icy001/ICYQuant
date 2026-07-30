"""测试 Schema Registry — Schema 注册中心。

覆盖: Schema 注册、版本管理、兼容性检查、数据验证。
"""

import pytest
from services.data_platform.schema_registry import (
    SchemaRegistry,
    SchemaDefinition,
    FieldDefinition,
    FieldType,
    SchemaCompatibility,
    CompatibilityReport,
    ValidationResult,
    SchemaRegistryConfig,
)


class TestSchemaRegistry:
    """测试 Schema 注册。"""

    @pytest.fixture
    def registry(self):
        return SchemaRegistry(SchemaRegistryConfig())

    @pytest.fixture
    def tick_schema(self):
        return SchemaDefinition(
            name="market_tick",
            version=1,
            description="Market tick data",
            fields=[
                FieldDefinition("symbol", FieldType.STRING, required=True),
                FieldDefinition("timestamp", FieldType.TIMESTAMP, required=True),
                FieldDefinition("price", FieldType.FLOAT, required=True),
                FieldDefinition("volume", FieldType.INTEGER),
            ],
            primary_key=["symbol", "timestamp"],
        )

    def test_register_schema(self, registry, tick_schema):
        """注册 Schema 应成功。"""
        result = registry.register("market_tick", tick_schema)
        assert result.name == "market_tick"
        assert result.version == 1

    def test_register_duplicate_version(self, registry, tick_schema):
        """注册重复版本应抛出异常。"""
        registry.register("market_tick", tick_schema)
        dup = SchemaDefinition(name="market_tick", version=1, fields=[])
        with pytest.raises(ValueError):
            registry.register("market_tick", dup)

    def test_get_latest(self, registry, tick_schema):
        """获取最新版本应返回最新注册的 Schema。"""
        registry.register("market_tick", tick_schema)
        latest = registry.get_latest("market_tick")
        assert latest is not None
        assert latest.version == 1

    def test_get_version(self, registry, tick_schema):
        """按版本号获取应返回正确版本。"""
        registry.register("market_tick", tick_schema)
        v1 = registry.get_version("market_tick", 1)
        assert v1 is not None
        assert v1.version == 1

    def test_list_versions(self, registry, tick_schema):
        """列出版本应返回所有版本。"""
        registry.register("market_tick", tick_schema)
        v2 = SchemaDefinition(
            name="market_tick", version=2,
            fields=tick_schema.fields + [FieldDefinition("bid", FieldType.FLOAT)],
        )
        registry.register("market_tick", v2)
        versions = registry.list_versions("market_tick")
        assert len(versions) == 2

    def test_list_all(self, registry, tick_schema):
        """列出所有 Schema 应包含所有注册的。"""
        registry.register("market_tick", tick_schema)
        bar = SchemaDefinition(
            name="market_bar", version=1,
            fields=[FieldDefinition("symbol", FieldType.STRING, required=True)],
        )
        registry.register("market_bar", bar)
        all_schemas = registry.list_all()
        assert len(all_schemas) == 2


class TestSchemaEvolution:
    """测试 Schema 演化。"""

    @pytest.fixture
    def registry(self):
        return SchemaRegistry(SchemaRegistryConfig())

    def test_evolve_schema(self, registry):
        """演化 Schema 应自动增加版本号。"""
        v1 = SchemaDefinition(
            name="test", version=1,
            fields=[FieldDefinition("a", FieldType.STRING, required=True)],
        )
        registry.register("test", v1)

        v2 = SchemaDefinition(
            name="test", version=1,
            fields=[
                FieldDefinition("a", FieldType.STRING, required=True),
                FieldDefinition("b", FieldType.INTEGER),
            ],
            compatibility=SchemaCompatibility.BACKWARD,
        )
        evolved = registry.evolve("test", v2)
        assert evolved.version == 2
        assert evolved.parent_schema == "test_v1"

    def test_evolve_nonexistent(self, registry):
        """演化不存在的 Schema 应抛出异常。"""
        new_schema = SchemaDefinition(name="nonexistent", fields=[])
        with pytest.raises(ValueError):
            registry.evolve("nonexistent", new_schema)


class TestSchemaCompatibility:
    """测试 Schema 兼容性检查。"""

    @pytest.fixture
    def registry(self):
        return SchemaRegistry(SchemaRegistryConfig())

    def test_backward_compatible_add_optional(self, registry):
        """向后兼容：添加可选字段应通过。"""
        old = SchemaDefinition(
            name="test", fields=[
                FieldDefinition("a", FieldType.STRING, required=True),
            ],
        )
        new = SchemaDefinition(
            name="test", fields=[
                FieldDefinition("a", FieldType.STRING, required=True),
                FieldDefinition("b", FieldType.INTEGER, required=False),
            ],
            compatibility=SchemaCompatibility.BACKWARD,
        )
        report = registry.check_compatibility(old, new)
        assert report.is_compatible

    def test_backward_incompatible_add_required(self, registry):
        """向后兼容：添加必需字段应失败。"""
        old = SchemaDefinition(
            name="test", fields=[
                FieldDefinition("a", FieldType.STRING, required=True),
            ],
        )
        new = SchemaDefinition(
            name="test", fields=[
                FieldDefinition("a", FieldType.STRING, required=True),
                FieldDefinition("b", FieldType.INTEGER, required=True),
            ],
            compatibility=SchemaCompatibility.BACKWARD,
        )
        report = registry.check_compatibility(old, new)
        assert not report.is_compatible

    def test_backward_incompatible_remove_field(self, registry):
        """向后兼容：删除字段应失败。"""
        old = SchemaDefinition(
            name="test", fields=[
                FieldDefinition("a", FieldType.STRING, required=True),
                FieldDefinition("b", FieldType.INTEGER),
            ],
        )
        new = SchemaDefinition(
            name="test", fields=[
                FieldDefinition("a", FieldType.STRING, required=True),
            ],
            compatibility=SchemaCompatibility.BACKWARD,
        )
        report = registry.check_compatibility(old, new)
        assert not report.is_compatible

    def test_type_change_incompatible(self, registry):
        """类型变更应不兼容。"""
        old = SchemaDefinition(
            name="test", fields=[
                FieldDefinition("a", FieldType.INTEGER),
            ],
        )
        new = SchemaDefinition(
            name="test", fields=[
                FieldDefinition("a", FieldType.STRING),
            ],
        )
        report = registry.check_compatibility(old, new)
        assert not report.is_compatible


class TestSchemaValidation:
    """测试 Schema 数据验证。"""

    @pytest.fixture
    def registry(self):
        reg = SchemaRegistry(SchemaRegistryConfig())
        schema = SchemaDefinition(
            name="test", version=1,
            fields=[
                FieldDefinition("symbol", FieldType.STRING, required=True),
                FieldDefinition("price", FieldType.FLOAT, required=True),
                FieldDefinition("volume", FieldType.INTEGER),
            ],
        )
        reg.register("test", schema)
        return reg

    def test_validate_valid_data(self, registry):
        """验证合法数据应通过。"""
        data = [
            {"symbol": "AAPL", "price": 150.0, "volume": 1000},
            {"symbol": "MSFT", "price": 300.0, "volume": 500},
        ]
        result = registry.validate("test", data)
        assert result.is_valid
        assert result.failed_count == 0

    def test_validate_missing_required(self, registry):
        """验证缺少必需字段应失败。"""
        data = [{"price": 150.0}]
        result = registry.validate("test", data)
        assert not result.is_valid
        assert result.failed_count >= 1

    def test_validate_type_mismatch(self, registry):
        """验证类型不匹配应失败。"""
        data = [{"symbol": "AAPL", "price": "not_a_number"}]
        result = registry.validate("test", data)
        assert not result.is_valid

    def test_validate_optional_field(self, registry):
        """验证可选字段缺失应通过。"""
        data = [{"symbol": "AAPL", "price": 150.0}]
        result = registry.validate("test", data)
        assert result.is_valid


class TestSchemaDeprecation:
    """测试 Schema 废弃。"""

    def test_deprecate_schema(self):
        """废弃 Schema 应标记为 deprecated。"""
        registry = SchemaRegistry(SchemaRegistryConfig())
        schema = SchemaDefinition(
            name="test", version=1,
            fields=[FieldDefinition("a", FieldType.STRING)],
        )
        registry.register("test", schema)
        assert registry.deprecate("test") is True
        assert registry.get_latest("test").is_deprecated
