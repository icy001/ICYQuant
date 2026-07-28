from services.data_governance import *


def test_data_quality():
    engine = DataQualityEngine()
    result = engine.check("market_data")
    assert result["quality"] == "good"


def test_data_quality_check():
    engine = DataQualityEngine()
    result = engine.check("position_data")
    assert result == {"quality": "good"}


def test_data_validation():
    engine = DataValidationEngine()
    result = engine.validate({"symbol": "AAPL", "price": 150.0})
    assert result == {"valid": True}


def test_data_catalog_register():
    engine = DataCatalogEngine()
    result = engine.register("daily_market_data")
    assert result == {"dataset": "daily_market_data"}


def test_metadata_manager():
    manager = MetadataManager()
    result = manager.describe("trade_history")
    assert result == {"metadata": "trade_history"}


def test_data_lineage():
    engine = DataLineageEngine()
    lineage_path = "market_data → factor_model → signal → order → trade → NAV"
    result = engine.trace(lineage_path)
    assert result == {"lineage": lineage_path}


def test_data_permission():
    manager = DataPermissionManager()
    assert manager.check("Researcher") is True
    assert manager.check("Trader") is True
    assert manager.check("RiskManager") is True
    assert manager.check("Investor") is True
    assert manager.check("Administrator") is True


def test_data_compliance_monitor():
    monitor = DataComplianceMonitor()
    result = monitor.scan("investor_pii_data")
    assert result == {"status": "safe"}


def test_data_quality_scoring():
    scoring = DataQualityScoring()
    result = scoring.score("trade_repository")
    assert result == 100


def test_data_governance_workflow():
    workflow = DataGovernanceWorkflow()
    result = workflow.approve("new_factor_dataset")
    assert result == {"approved": True}


def test_data_governance_memory():
    memory = DataGovernanceMemory()
    assert memory.history == []
    memory.save({"event": "data_quality_check", "dataset": "market_data", "result": "good"})
    memory.save({"event": "catalog_registered", "dataset": "trade_history"})
    assert len(memory.history) == 2
    assert memory.history[0]["event"] == "data_quality_check"
    assert memory.history[1]["event"] == "catalog_registered"


def test_data_governance_service():
    quality = DataQualityEngine()
    service = DataGovernanceService(quality=quality)
    result = service.check("position_snapshot")
    assert result == {"quality": "good"}


def test_full_data_governance_workflow():
    """End-to-end data governance workflow."""
    # 1. Quality check
    quality_engine = DataQualityEngine()
    quality = quality_engine.check("market_data_feed")
    assert quality["quality"] == "good"

    # 2. Validate data
    validator = DataValidationEngine()
    validation = validator.validate({"symbol": "NVDA", "price": 450.25, "timestamp": "2024-01-15"})
    assert validation["valid"] is True

    # 3. Register in catalog
    catalog = DataCatalogEngine()
    registered = catalog.register("market_data_feed")
    assert registered["dataset"] == "market_data_feed"

    # 4. Describe metadata
    metadata = MetadataManager()
    meta = metadata.describe("market_data_feed")
    assert meta["metadata"] == "market_data_feed"

    # 5. Trace lineage
    lineage = DataLineageEngine()
    trace = lineage.trace("raw_market → cleaned → factor_engine → signal_generator")
    assert trace["lineage"] == "raw_market → cleaned → factor_engine → signal_generator"

    # 6. Check permissions
    perm = DataPermissionManager()
    assert perm.check("Researcher") is True

    # 7. Compliance scan
    compliance = DataComplianceMonitor()
    scan = compliance.scan("market_data_feed")
    assert scan["status"] == "safe"

    # 8. Score quality
    scoring = DataQualityScoring()
    score = scoring.score("market_data_feed")
    assert score == 100

    # 9. Approve workflow
    workflow = DataGovernanceWorkflow()
    approved = workflow.approve("market_data_feed")
    assert approved["approved"] is True

    # 10. Save to governance memory
    memory = DataGovernanceMemory()
    memory.save({"event": "dataset_approved", "dataset": "market_data_feed"})
    memory.save({"event": "quality_check_passed", "score": 100})
    assert len(memory.history) == 2

    # 11. Governance service
    service = DataGovernanceService(quality=quality_engine)
    svc_result = service.check("factor_library")
    assert svc_result["quality"] == "good"
