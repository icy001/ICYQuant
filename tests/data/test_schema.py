from services.data.schema import (
    SchemaField,
    DatasetSchema,
    SchemaRegistry,
    DataContract,
    SchemaValidator,
    SchemaEvolutionChecker,
    SchemaGovernanceService,
)


def test_schema_registry():
    schema = DatasetSchema(
        name="NVDA_PRICE",
        version="v1",
        fields=[SchemaField("price", "float")],
    )

    registry = SchemaRegistry()

    registry.register(schema)

    result = registry.get("NVDA_PRICE", "v1")

    assert result.name == "NVDA_PRICE"


def test_schema_field():
    field = SchemaField(name="close_price", dtype="float", nullable=False)

    assert field.name == "close_price"
    assert field.dtype == "float"
    assert field.nullable is False


def test_schema_field_nullable():
    field = SchemaField(name="optional_field", dtype="str", nullable=True)

    assert field.nullable is True


def test_dataset_schema():
    schema = DatasetSchema(
        name="NASDAQ_TICK_SCHEMA",
        version="v1.0",
        fields=[
            SchemaField("price", "float"),
            SchemaField("volume", "int"),
        ],
    )

    assert schema.name == "NASDAQ_TICK_SCHEMA"
    assert schema.version == "v1.0"
    assert len(schema.fields) == 2


def test_data_contract():
    schema = DatasetSchema(
        name="TEST_SCHEMA",
        version="v1",
        fields=[SchemaField("value", "float")],
    )
    contract = DataContract(
        producer="MarketDataService",
        consumer="FeatureEngine",
        schema=schema,
    )

    assert contract.producer == "MarketDataService"
    assert contract.consumer == "FeatureEngine"


def test_schema_validator_pass():
    schema = DatasetSchema(
        name="TEST",
        version="v1",
        fields=[SchemaField("price", "float")],
    )
    validator = SchemaValidator()

    result = validator.validate(schema, {"price": 100.0})

    assert result is True


def test_schema_validator_fail():
    schema = DatasetSchema(
        name="TEST",
        version="v1",
        fields=[SchemaField("price", "float")],
    )
    validator = SchemaValidator()

    result = validator.validate(schema, {})

    assert result is False


def test_schema_evolution_compatible():
    old_schema = DatasetSchema(
        name="TEST",
        version="v1",
        fields=[SchemaField("price", "float"), SchemaField("volume", "int")],
    )
    new_schema = DatasetSchema(
        name="TEST",
        version="v2",
        fields=[
            SchemaField("price", "float"),
            SchemaField("volume", "int"),
            SchemaField("turnover", "float"),
        ],
    )
    checker = SchemaEvolutionChecker()

    result = checker.compatible(old_schema, new_schema)

    assert result is True


def test_schema_evolution_incompatible():
    old_schema = DatasetSchema(
        name="TEST",
        version="v1",
        fields=[SchemaField("price", "float")],
    )
    new_schema = DatasetSchema(
        name="TEST",
        version="v2",
        fields=[SchemaField("close", "float")],
    )
    checker = SchemaEvolutionChecker()

    result = checker.compatible(old_schema, new_schema)

    assert result is False


def test_schema_governance_service():
    registry = SchemaRegistry()
    validator = SchemaValidator()
    evolution = SchemaEvolutionChecker()
    service = SchemaGovernanceService(registry, validator, evolution)

    schema = DatasetSchema(
        name="GOVERNANCE_TEST",
        version="v1",
        fields=[SchemaField("value", "float")],
    )

    service.register_schema(schema)

    result = registry.get("GOVERNANCE_TEST", "v1")

    assert result.name == "GOVERNANCE_TEST"