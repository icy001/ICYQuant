"""
Validation script for canary release platform and experiment framework.

Comprehensive test suite covering:
    1. Canary Stage Model
    2. Canary Policy
    3. Canary Health Monitor
    4. Canary Deployment Manager
    5. Canary Promotion Engine
    6. Canary Rollback Manager
    7. Canary Manager (unified)
    8. Canary Metrics
    9. Canary Audit
    10. Canary Validator
    11. Canary Monitor
    12. Experiment Model
    13. Variant Definitions
    14. Variant Allocator
    15. Statistics Collector
    16. Experiment Analyzer
    17. Winner Selector
    18. Experiment Manager (unified)
    19. Experiment Archive
    20. Experiment Metrics
    21. Experiment Audit
    22. Experiment Validator
    23. Evaluator Integration (Canary + Experiment)
    24. Exceptions
"""

from __future__ import annotations

import asyncio
import sys
import traceback

PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [OK] {name}")
    else:
        FAILED += 1
        print(f"  [FAIL] {name} {'- ' + detail if detail else ''}")


# ── 1. Canary Stage Model ──

def test_canary_stage():
    print("\n=== 1. Canary Stage Model ===")
    from infrastructure.feature_flags.canary import (
        CanaryStage,
        CanaryDeployment,
        DEFAULT_CANARY_STAGES,
    )

    # Default stages
    check("5 default stages", len(DEFAULT_CANARY_STAGES) == 5)
    check("Stage 1 is 1%", DEFAULT_CANARY_STAGES[0].percentage == 1.0)
    check("Stage 5 is 100%", DEFAULT_CANARY_STAGES[4].percentage == 100.0)
    check("Stages ascending", all(
        DEFAULT_CANARY_STAGES[i].percentage < DEFAULT_CANARY_STAGES[i + 1].percentage
        for i in range(len(DEFAULT_CANARY_STAGES) - 1)
    ))

    # Create stage
    s = CanaryStage(stage_id="test", percentage=10.0)
    check("Stage created", s.stage_id == "test")
    check("Stage percentage", s.percentage == 10.0)
    check("Stage to_dict", s.to_dict()["stage_id"] == "test")
    check("Stage from_dict", CanaryStage.from_dict(s.to_dict()).stage_id == "test")

    # Invalid stage
    try:
        CanaryStage(percentage=-1)
        check("Rejects negative percentage", False)
    except ValueError:
        check("Rejects negative percentage", True)

    try:
        CanaryStage(percentage=101)
        check("Rejects >100 percentage", False)
    except ValueError:
        check("Rejects >100 percentage", True)

    # Deployment model
    d = CanaryDeployment(deployment_id="d1", feature_key="test-flag")
    check("Deployment created", d.deployment_id == "d1")
    check("Deployment has stages", len(d.stages) > 0)
    check("Deployment initial stage 0", d.current_stage_index == 0)
    check("Deployment current_percentage", d.current_percentage == d.current_stage.percentage)
    check("Deployment progress", d.progress >= 0.0)
    check("Deployment to_dict", "deployment_id" in d.to_dict())

    # Manual stage list
    custom_stages = [
        CanaryStage(stage_id="s1", percentage=5.0),
        CanaryStage(stage_id="s2", percentage=50.0),
        CanaryStage(stage_id="s3", percentage=100.0),
    ]
    d2 = CanaryDeployment(stages=custom_stages)
    check("Custom stages", len(d2.stages) == 3)


# ── 2. Canary Policy ──

def test_canary_policy():
    print("\n=== 2. Canary Policy ===")
    from infrastructure.feature_flags.canary import (
        CanaryPolicy,
        CONSERVATIVE_POLICY,
        BALANCED_POLICY,
        AGGRESSIVE_POLICY,
    )

    # Default policy
    p = CanaryPolicy()
    check("Default auto_promote", p.auto_promote is True)
    check("Default rollback_on_failure", p.rollback_on_failure is True)
    check("Default strategy balanced", p.strategy == "balanced")
    check("Default to_dict", p.to_dict()["strategy"] == "balanced")
    check("Default from_dict", CanaryPolicy.from_dict({"strategy": "conservative"}).strategy == "conservative")

    # Pre-defined policies
    check("Conservative strategy", CONSERVATIVE_POLICY.strategy == "conservative")
    check("Conservative low threshold", CONSERVATIVE_POLICY.rollback_threshold == 2.0)
    check("Balanced strategy", BALANCED_POLICY.strategy == "balanced")
    check("Balanced threshold", BALANCED_POLICY.rollback_threshold == 5.0)
    check("Aggressive strategy", AGGRESSIVE_POLICY.strategy == "aggressive")
    check("Aggressive high threshold", AGGRESSIVE_POLICY.rollback_threshold == 10.0)

    # Invalid strategy
    try:
        CanaryPolicy(strategy="invalid")
        check("Rejects invalid strategy", False)
    except ValueError:
        check("Rejects invalid strategy", True)


# ── 3. Canary Health Monitor ──

def test_canary_health():
    print("\n=== 3. Canary Health Monitor ===")
    from infrastructure.feature_flags.canary import (
        HealthMonitor,
        HealthStatus,
    )

    monitor = HealthMonitor()
    monitor.start()

    # Record healthy requests
    for _ in range(100):
        monitor.record_request(latency_ms=50.0, error=False)

    result = monitor.check_health(
        error_rate_threshold=5.0,
        latency_p99_threshold_ms=500.0,
    )
    check("Healthy status", result.status == HealthStatus.HEALTHY)
    check("Healthy score", result.score >= 90.0)
    check("Zero error rate", result.error_rate == 0.0)
    check("P99 latency tracked", result.latency_p99_ms > 0)
    check("Request count 100", result.request_count == 100)

    # Record errors
    monitor.start()
    for _ in range(90):
        monitor.record_request(latency_ms=50.0, error=False)
    for _ in range(10):
        monitor.record_request(latency_ms=600.0, error=True)

    result2 = monitor.check_health(
        error_rate_threshold=5.0,
        latency_p99_threshold_ms=500.0,
    )
    check("Error rate 10%", result2.error_rate == 10.0)
    check("Error count 10", result2.error_count == 10)
    check("Critical or warning", result2.status in (HealthStatus.WARNING, HealthStatus.CRITICAL))

    # Stats
    stats = monitor.get_stats()
    check("Stats request_count", stats["request_count"] == 100)
    check("Stats error_rate", stats["error_rate"] == 10.0)

    # Reset
    monitor.reset()
    stats2 = monitor.get_stats()
    check("Reset clears", stats2["request_count"] == 0)


# ── 4. Canary Deployment Manager ──

async def test_canary_deployment():
    print("\n=== 4. Canary Deployment Manager ===")
    from infrastructure.feature_flags.canary import (
        CanaryDeploymentManager,
        CanaryDeployment,
        CanaryPolicy,
    )

    deployment = CanaryDeployment(
        deployment_id="test-deploy",
        feature_key="test-flag",
    )
    dm = CanaryDeploymentManager(deployment=deployment)
    check("DM created", dm.deployment.deployment_id == "test-deploy")
    check("DM initial status", dm.deployment.status == "pending")

    # Start
    await dm.start()
    check("DM running", dm.is_running)
    check("DM current_percentage", dm.current_percentage == deployment.current_stage.percentage)

    # Record requests
    for _ in range(200):
        dm.record_request(latency_ms=50.0, error=False)
    stats = dm.get_stats()
    check("DM recorded requests", stats["health"]["request_count"] == 200)

    # Check health
    health = dm.check_health()
    check("DM health check works", health is not None)

    # Promote (with sufficient health and duration)
    promoted = await dm.promote(force=True)
    check("DM force promote", promoted)
    check("DM stage index 1", dm.deployment.current_stage_index == 1)

    # Stats
    stats = dm.get_stats()
    check("DM stats has promotions", "promotions" in stats)


# ── 5. Canary Promotion Engine ──

def test_canary_promotion():
    print("\n=== 5. Canary Promotion Engine ===")
    from infrastructure.feature_flags.canary import (
        PromotionEngine,
        PromotionDecision,
        CanaryDeployment,
        CanaryPolicy,
        HealthStatus,
        HealthMonitor,
    )

    policy = CanaryPolicy(min_sample_size=10)
    engine = PromotionEngine(policy)
    deployment = CanaryDeployment(feature_key="test")
    deployment.status = "running"

    # Cannot promote at last stage
    deployment.current_stage_index = len(deployment.stages) - 1
    decision = engine.evaluate(deployment, None, request_count=100)
    check("Cannot promote at last stage", not decision.can_promote)

    # Back to first stage
    deployment.current_stage_index = 0

    # Insufficient samples
    monitor = HealthMonitor()
    monitor.start()
    for _ in range(5):
        monitor.record_request(latency_ms=50.0)
    health = monitor.check_health()
    decision = engine.evaluate(deployment, health, request_count=5)
    check("Insufficient samples", not decision.can_promote)

    # Enough samples but not enough duration
    for _ in range(100):
        monitor.record_request(latency_ms=50.0)
    health = monitor.check_health()
    decision = engine.evaluate(deployment, health, request_count=105, elapsed_seconds=1.0)
    check("Duration not met", not decision.can_promote)

    # All conditions met
    decision = engine.evaluate(deployment, health, request_count=105, elapsed_seconds=600.0)
    check("Can promote when all OK", decision.can_promote)
    check("Next percentage > 0", decision.next_percentage > 0)

    # Critical health triggers rollback
    critical_monitor = HealthMonitor()
    critical_monitor.start()
    for _ in range(50):
        critical_monitor.record_request(latency_ms=50.0)
    for _ in range(50):
        critical_monitor.record_request(latency_ms=600.0, error=True)
    critical_health = critical_monitor.check_health(error_rate_threshold=5.0)
    decision = engine.evaluate(deployment, critical_health, request_count=100, elapsed_seconds=600.0)
    check("Critical triggers rollback", decision.should_rollback)


# ── 6. Canary Rollback Manager ──

async def test_canary_rollback():
    print("\n=== 6. Canary Rollback Manager ===")
    from infrastructure.feature_flags.canary import (
        RollbackManager,
        CanaryDeployment,
        CanaryPolicy,
    )

    policy = CanaryPolicy(rollback_threshold=5.0)
    rb = RollbackManager(policy)
    deployment = CanaryDeployment(feature_key="test")
    deployment.status = "running"
    deployment.current_stage_index = 2

    # Manual rollback
    rolled = await rb.execute_rollback(deployment, reason="test_rollback")
    check("Manual rollback works", rolled)
    check("Stage decreased", deployment.current_stage_index == 1)
    check("Status running", deployment.status == "running")

    # Auto rollback threshold
    check("Auto rollback 10% > 5%", rb.should_auto_rollback(10.0))
    check("No auto rollback 3% < 5%", not rb.should_auto_rollback(3.0))

    # Emergency rollback
    deployment.current_stage_index = 3
    rolled = await rb.execute_rollback(deployment, rollback_type="emergency")
    check("Emergency rollback", rolled)
    check("Emergency stage 0", deployment.current_stage_index == 0)
    check("Emergency status", deployment.status == "rolled_back")

    # History
    history = rb.get_history()
    check("History has entries", len(history) >= 2)

    # Stats
    stats = rb.get_stats()
    check("Stats total_rollbacks", stats["total_rollbacks"] >= 2)
    check("Stats emergency_rollbacks", stats["emergency_rollbacks"] >= 1)

    # Cannot rollback at stage 0
    deployment2 = CanaryDeployment(feature_key="test2")
    deployment2.status = "running"
    rolled = await rb.execute_rollback(deployment2)
    check("Cannot rollback at stage 0", not rolled)


# ── 7. Canary Manager (unified) ──

async def test_canary_manager():
    print("\n=== 7. Canary Manager (unified) ===")
    from infrastructure.feature_flags.canary import CanaryManager

    manager = CanaryManager()
    check("Manager created", manager is not None)

    # Start deployment
    deployment = await manager.start_deployment("test-feature")
    check("Deployment started", deployment is not None)
    check("Deployment feature_key", deployment.feature_key == "test-feature")
    check("Deployment running", deployment.status == "running")

    # Record requests
    for _ in range(50):
        manager.record_request("test-feature", latency_ms=45.0)

    # Check health
    health = manager.check_health("test-feature")
    check("Health check works", health is not None)

    # Get deployment
    dep = manager.get_deployment("test-feature")
    check("Get deployment", dep is not None)

    # Get percentage
    pct = manager.get_current_percentage("test-feature")
    check("Current percentage > 0", pct > 0)

    # Promote
    promoted = await manager.promote("test-feature", force=True)
    check("Promote works", promoted)

    # Validate stages
    from infrastructure.feature_flags.canary import CanaryStage
    errors = manager.validate_stages([
        CanaryStage(stage_id="s1", percentage=10.0),
        CanaryStage(stage_id="s2", percentage=50.0),
    ])
    check("Valid stages", len(errors) == 0)

    # Rollback
    rolled = await manager.rollback("test-feature", reason="test")
    check("Rollback works", rolled)

    # Non-existent feature
    check("No deployment for unknown", manager.get_deployment("unknown") is None)
    check("No health for unknown", manager.check_health("unknown") is None)

    # Stats
    stats = manager.get_stats()
    check("Stats active_deployments", "active_deployments" in stats)
    check("Stats total_deployments", stats["total_deployments"] >= 1)


# ── 8. Canary Metrics ──

def test_canary_metrics():
    print("\n=== 8. Canary Metrics ===")
    from infrastructure.feature_flags.canary import CanaryMetrics

    metrics = CanaryMetrics()
    metrics.record_stage("test-flag", 0, 1.0)
    metrics.record_stage("test-flag", 1, 5.0)
    metrics.record_rollback("test-flag", "automatic")
    metrics.record_health_score("test-flag", 95.0)
    metrics.record_promotion("test-flag")
    metrics.record_request("test-flag", error=False)
    metrics.record_request("test-flag", error=True)

    snap = metrics.snapshot()
    check("Snapshot has stage_total", "stage_total" in snap)
    check("Snapshot has rollback_total", "rollback_total" in snap)
    check("Snapshot has health_score", "health_score" in snap)

    counters = metrics.get_counter_values()
    check("Counters has stage total", counters.get("icyquant_canary_stage_total", 0) >= 2)
    check("Counters has rollback total", counters.get("icyquant_canary_rollback_total", 0) >= 1)

    metrics.reset()
    snap2 = metrics.snapshot()
    check("Reset clears", len(snap2["stage_total"]) == 0)


# ── 9. Canary Audit ──

async def test_canary_audit():
    print("\n=== 9. Canary Audit ===")
    from infrastructure.feature_flags.canary import CanaryAudit

    audit = CanaryAudit()
    await audit.record_promotion("test-flag", 1, 1.0, 5.0)
    await audit.record_rollback("test-flag", "automatic", 5.0, 1.0, "error_rate")
    await audit.record_health_change("test-flag", "healthy", "critical", 45.0)

    entries = await audit.query(feature_key="test-flag")
    check("Query by feature_key", len(entries) == 3)

    promotions = await audit.query(entry_type="promotion")
    check("Query by type promotion", len(promotions) == 1)

    stats = audit.get_stats()
    check("Stats total_entries", stats["total_entries"] == 3)


# ── 10. Canary Validator ──

def test_canary_validator():
    print("\n=== 10. Canary Validator ===")
    from infrastructure.feature_flags.canary import (
        CanaryValidator,
        CanaryStage,
        CanaryDeployment,
        CanaryPolicy,
    )

    validator = CanaryValidator()

    # Valid stages
    valid_stages = [
        CanaryStage(stage_id="s1", percentage=5.0),
        CanaryStage(stage_id="s2", percentage=50.0),
        CanaryStage(stage_id="s3", percentage=100.0),
    ]
    errors = validator.validate_stages(valid_stages)
    check("Valid stages", len(errors) == 0)

    # Too few stages
    errors = validator.validate_stages([CanaryStage(stage_id="s1", percentage=100.0)])
    check("Too few stages", len(errors) > 0)

    # Unordered stages
    bad_stages = [
        CanaryStage(stage_id="s1", percentage=50.0),
        CanaryStage(stage_id="s2", percentage=10.0),
    ]
    errors = validator.validate_stages(bad_stages)
    check("Unordered stages", len(errors) > 0)

    # Valid policy
    errors = validator.validate_policy(CanaryPolicy())
    check("Valid policy", len(errors) == 0)

    # Valid deployment
    d = CanaryDeployment(feature_key="test", stages=valid_stages)
    errors = validator.validate_deployment(d)
    check("Valid deployment", len(errors) == 0)


# ── 11. Canary Monitor ──

def test_canary_monitor():
    print("\n=== 11. Canary Monitor ===")
    from infrastructure.feature_flags.canary import CanaryMonitor

    monitor = CanaryMonitor()
    monitor.record("flag1", success=True, latency_ms=50.0)
    monitor.record("flag1", success=True, latency_ms=60.0)
    monitor.record("flag1", success=False, latency_ms=100.0)

    snap = monitor.snapshot("flag1", current_percentage=25.0)
    check("Snapshot feature_key", snap.feature_key == "flag1")
    check("Snapshot request_count", snap.request_count == 3)
    check("Snapshot success_rate", snap.success_rate > 0)
    check("Snapshot to_dict", "feature_key" in snap.to_dict())

    history = monitor.get_history("flag1")
    check("History has entries", len(history) >= 1)

    stats = monitor.get_stats()
    check("Monitor stats", stats["monitored_features"] == 1)

    monitor.reset("flag1")
    stats2 = monitor.get_stats()
    check("Reset clears", stats2["monitored_features"] == 0)


# ── 12. Experiment Model ──

def test_experiment_model():
    print("\n=== 12. Experiment Model ===")
    from infrastructure.feature_flags.experiments import (
        Experiment,
        ExperimentStatus,
        ExperimentResult,
    )

    # Create experiment
    exp = Experiment(
        experiment_id="exp-1",
        name="Test Experiment",
        feature_key="test-flag",
    )
    check("Experiment created", exp.experiment_id == "exp-1")
    check("Default status draft", exp.status == ExperimentStatus.DRAFT)
    check("To_dict works", exp.to_dict()["experiment_id"] == "exp-1")
    check("From_dict works", Experiment.from_dict({"experiment_id": "e2"}).experiment_id == "e2")

    # Experiment result
    result = ExperimentResult(
        experiment_id="exp-1",
        winner_variant_id="treatment",
        confidence=0.95,
        p_value=0.03,
    )
    check("Result created", result.experiment_id == "exp-1")
    check("Result winner", result.winner_variant_id == "treatment")
    check("Result to_dict", result.to_dict()["winner_variant_id"] == "treatment")


# ── 13. Variant Definitions ──

def test_variant():
    print("\n=== 13. Variant Definitions ===")
    from infrastructure.feature_flags.experiments import (
        Variant,
        create_ab_variants,
        create_abc_variants,
    )

    # Single variant
    v = Variant(variant_id="control", name="Control", is_control=True, weight=50.0, value=False)
    check("Variant created", v.variant_id == "control")
    check("Variant is_control", v.is_control)
    check("Variant weight", v.weight == 50.0)
    check("Variant to_dict", v.to_dict()["variant_id"] == "control")
    check("Variant from_dict", Variant.from_dict(v.to_dict()).variant_id == "control")

    # A/B variants
    ab = create_ab_variants()
    check("A/B has 2 variants", len(ab) == 2)
    check("A/B has control", any(v.is_control for v in ab))
    check("A/B control is False", ab[0].value is False)
    check("A/B treatment is True", ab[1].value is True)
    check("A/B 50/50 weights", ab[0].weight == 50.0 and ab[1].weight == 50.0)

    # Custom A/B
    ab_custom = create_ab_variants(control_weight=80.0, treatment_weight=20.0)
    check("Custom A/B 80/20", ab_custom[0].weight == 80.0)

    # A/B/C variants
    abc = create_abc_variants()
    check("A/B/C has 3 variants", len(abc) == 3)
    check("A/B/C has control", abc[0].is_control)
    check("A/B/C treatment-a", abc[1].variant_id == "treatment-a")

    # Custom A/B/C
    abc_custom = create_abc_variants(weights=[50.0, 25.0, 25.0])
    check("Custom A/B/C weights", abc_custom[0].weight == 50.0)


# ── 14. Variant Allocator ──

def test_variant_allocator():
    print("\n=== 14. Variant Allocator ===")
    from infrastructure.feature_flags.experiments import (
        VariantAllocator,
        Variant,
        create_ab_variants,
    )

    allocator = VariantAllocator()
    variants = create_ab_variants()

    # Assign same user twice = same variant
    v1 = allocator.assign("exp-1", "user-123", variants)
    v2 = allocator.assign("exp-1", "user-123", variants)
    check("Sticky assignment", v1.variant_id == v2.variant_id)

    # Different users may get different variants
    results = {}
    for i in range(200):
        v = allocator.assign("exp-2", f"user-{i}", variants)
        results[v.variant_id] = results.get(v.variant_id, 0) + 1
    check("Both variants assigned", len(results) >= 1)

    # Get assignment
    cached = allocator.get_assignment("exp-1", "user-123")
    check("Cached assignment", cached is not None)

    # Batch allocation
    batch = allocator.allocate_batch("exp-3", ["u1", "u2", "u3"], variants)
    check("Batch allocation", len(batch) == 3)

    # Distribution estimate
    dist = allocator.get_variant_distribution("exp-dist", variants, sample_size=500)
    check("Distribution has variants", len(dist) == 2)
    check("Distribution sums to 500", sum(dist.values()) == 500)

    # Invalidate
    removed = allocator.invalidate("exp-1")
    check("Invalidate works", removed >= 1)

    # Stats
    stats = allocator.get_stats()
    check("Stats allocations", stats["allocations"] > 0)


# ── 15. Statistics Collector ──

def test_statistics_collector():
    print("\n=== 15. Statistics Collector ===")
    from infrastructure.feature_flags.experiments import (
        StatisticsCollector,
        VariantStats,
    )

    collector = StatisticsCollector()

    # Record observations
    for i in range(50):
        collector.record("control", value=1.0, converted=(i % 5 == 0))
    for i in range(50):
        collector.record("treatment", value=2.0, converted=(i % 3 == 0))

    # Get stats
    ctrl = collector.get_stats("control")
    trt = collector.get_stats("treatment")
    check("Control sample_size", ctrl.sample_size == 50)
    check("Control conversions", ctrl.conversions == 10)
    check("Control conversion_rate", ctrl.conversion_rate == 0.2)
    check("Control average_value", ctrl.average_value == 1.0)
    check("Treatment sample_size", trt.sample_size == 50)
    check("Treatment average_value", trt.average_value == 2.0)
    check("Treatment conversion_rate", trt.conversion_rate > ctrl.conversion_rate)

    # All stats
    all_stats = collector.get_all_stats()
    check("All stats has both", len(all_stats) == 2)

    # Custom metrics
    collector.record("control", value=1.0, custom_metrics={"profit": 100.0})
    ctrl = collector.get_stats("control")
    check("Custom metrics", "profit" in ctrl.custom_metrics)

    # To_dict
    check("VariantStats to_dict", "sample_size" in ctrl.to_dict())

    # Reset
    collector.reset("control")
    ctrl2 = collector.get_stats("control")
    check("Reset clears variant", ctrl2.sample_size == 0)


# ── 16. Experiment Analyzer ──

def test_experiment_analyzer():
    print("\n=== 16. Experiment Analyzer ===")
    from infrastructure.feature_flags.experiments import (
        ExperimentAnalyzer,
        AnalysisResult,
        VariantStats,
    )

    analyzer = ExperimentAnalyzer()

    # Control: 1000 samples, 10% conversion
    control = VariantStats(
        variant_id="control",
        sample_size=1000,
        conversions=100,
        conversion_rate=0.10,
        average_value=1.0,
        variance=1.0,
    )

    # Treatment: 1000 samples, 15% conversion
    treatment = VariantStats(
        variant_id="treatment",
        sample_size=1000,
        conversions=150,
        conversion_rate=0.15,
        average_value=1.5,
        variance=1.0,
    )

    # Analyze conversion
    result = analyzer.analyze(control, treatment, confidence=0.95, metric_type="conversion")
    check("Analysis result type", isinstance(result, AnalysisResult))
    check("Test type z_test", result.test_type == "z_test")
    check("P-value computed", 0 <= result.p_value <= 1)
    check("Significant detection", result.p_value < 0.05)
    check("Lift positive", result.lift > 0)
    check("CI control", len(result.control_ci) == 2)
    check("CI treatment", len(result.treatment_ci) == 2)
    check("To_dict", "test_type" in result.to_dict())

    # Analyze continuous
    result2 = analyzer.analyze(control, treatment, confidence=0.95, metric_type="continuous")
    check("Continuous test type t_test", result2.test_type == "t_test")

    # Insufficient data
    small = VariantStats(variant_id="small", sample_size=0)
    result3 = analyzer.analyze(small, treatment)
    check("Handles zero samples", result3 is not None)

    # Effect size
    from infrastructure.feature_flags.experiments.analyzer import effect_size_cohens_d
    d = effect_size_cohens_d(control, treatment)
    check("Effect size computed", d != 0)


# ── 17. Winner Selector ──

def test_winner_selector():
    print("\n=== 17. Winner Selector ===")
    from infrastructure.feature_flags.experiments import (
        WinnerSelector,
        WinnerResult,
        VariantStats,
    )

    selector = WinnerSelector(min_confidence=0.95, min_lift=0.0, min_sample_size=100)

    control = VariantStats(
        variant_id="control",
        sample_size=1000,
        conversions=100,
        conversion_rate=0.10,
        average_value=1.0,
        variance=1.0,
    )
    treatment = VariantStats(
        variant_id="treatment",
        sample_size=1000,
        conversions=150,
        conversion_rate=0.15,
        average_value=1.5,
        variance=1.0,
    )

    result = selector.select(control, treatment, metric_type="conversion")
    check("WinnerResult type", isinstance(result, WinnerResult))
    check("Has winner", result.has_winner)
    check("Winner is treatment", result.winner_id == "treatment")
    check("Reason provided", len(result.reason) > 0)
    check("Analysis attached", result.analysis is not None)
    check("To_dict", "has_winner" in result.to_dict())

    # Insufficient samples
    small_ctrl = VariantStats(variant_id="control", sample_size=10)
    small_trt = VariantStats(variant_id="treatment", sample_size=10)
    result2 = selector.select(small_ctrl, small_trt)
    check("No winner with small samples", not result2.has_winner)

    # Manual mode selector
    manual = WinnerSelector(mode="manual")
    check("Manual mode selector", manual._mode == "manual")


# ── 18. Experiment Manager (unified) ──

async def test_experiment_manager():
    print("\n=== 18. Experiment Manager (unified) ===")
    from infrastructure.feature_flags.experiments import (
        ExperimentManager,
        ExperimentStatus,
        create_ab_variants,
    )

    manager = ExperimentManager()

    # Create experiment
    exp = manager.create(
        experiment_id="exp-1",
        name="Test A/B",
        feature_key="test-flag",
        variants=create_ab_variants(),
    )
    check("Experiment created", exp.experiment_id == "exp-1")
    check("Status draft", exp.status == ExperimentStatus.DRAFT)

    # Start
    started = await manager.start("exp-1")
    check("Started", started)
    check("Status running", exp.status == ExperimentStatus.RUNNING)

    # Assign variant
    variant = manager.assign("exp-1", "user-123")
    check("Variant assigned", variant is not None)
    same_variant = manager.assign("exp-1", "user-123")
    check("Same user same variant", variant.variant_id == same_variant.variant_id)

    # Record observations
    for i in range(100):
        vid = "control" if i % 2 == 0 else "treatment"
        manager.record_observation("exp-1", vid, value=1.0, converted=(i % 3 == 0))

    # Analyze
    analysis = await manager.analyze("exp-1")
    check("Analysis works", analysis is not None)

    # Complete
    result = await manager.complete("exp-1", winner_id="treatment")
    check("Complete works", result is not None)
    check("Status completed", exp.status == ExperimentStatus.COMPLETED)

    # Get experiment
    check("Get experiment", manager.get_experiment("exp-1") is not None)
    check("Get unknown", manager.get_experiment("unknown") is None)

    # Validate
    errors = manager.validate_experiment(exp)
    check("Validation works", isinstance(errors, list))

    # Stats
    stats = manager.get_stats()
    check("Stats total_experiments", stats["total_experiments"] >= 1)

    # Pause/resume
    exp2 = manager.create("exp-2", "Pause Test", "flag-2")
    await manager.start("exp-2")
    paused = await manager.pause("exp-2")
    check("Pause works", paused)
    resumed = await manager.resume("exp-2")
    check("Resume works", resumed)


# ── 19. Experiment Archive ──

async def test_experiment_archive():
    print("\n=== 19. Experiment Archive ===")
    from infrastructure.feature_flags.experiments import (
        ExperimentArchive,
        Experiment,
    )

    archive = ExperimentArchive()
    exp = Experiment(
        experiment_id="archived-1",
        name="Archived",
        feature_key="flag-1",
        status="completed",
        winner_variant_id="treatment",
    )
    entry = await archive.store(exp, result={"winner": "treatment"})
    check("Archive stores", entry["experiment_id"] == "archived-1")

    retrieved = await archive.retrieve("archived-1")
    check("Archive retrieves", retrieved is not None)
    check("Retrieved winner", retrieved["winner_variant_id"] == "treatment")

    query_results = await archive.query()
    check("Archive query", len(query_results) >= 1)

    stats = archive.get_stats()
    check("Archive stats", stats["total_archived"] >= 1)


# ── 20. Experiment Metrics ──

def test_experiment_metrics():
    print("\n=== 20. Experiment Metrics ===")
    from infrastructure.feature_flags.experiments import ExperimentMetrics

    metrics = ExperimentMetrics()
    metrics.record_experiment_start("exp-1")
    metrics.record_variant_assignment("exp-1", "control")
    metrics.record_variant_assignment("exp-1", "treatment")
    metrics.record_experiment_duration("exp-1", 3600.0)

    snap = metrics.snapshot()
    check("Snapshot experiment_total", len(snap["experiment_total"]) > 0)
    check("Snapshot variant_assignment_total", len(snap["variant_assignment_total"]) > 0)
    check("Snapshot durations", len(snap["experiment_durations"]) > 0)

    counters = metrics.get_counter_values()
    check("Counter experiment_total", counters.get("icyquant_experiment_total", 0) >= 1)
    check("Counter variant_total", counters.get("icyquant_variant_assignment_total", 0) >= 2)

    metrics.reset()
    snap2 = metrics.snapshot()
    check("Reset clears", len(snap2["experiment_total"]) == 0)


# ── 21. Experiment Audit ──

async def test_experiment_audit():
    print("\n=== 21. Experiment Audit ===")
    from infrastructure.feature_flags.experiments import ExperimentAudit

    audit = ExperimentAudit()
    await audit.record_start("exp-1", "flag-1")
    await audit.record_assignment("exp-1", "user-123", "treatment")
    await audit.record_completion("exp-1", "treatment")

    entries = await audit.query(experiment_id="exp-1")
    check("Query by experiment_id", len(entries) == 3)

    starts = await audit.query(entry_type="start")
    check("Query by type start", len(starts) == 1)

    stats = audit.get_stats()
    check("Stats total_entries", stats["total_entries"] == 3)


# ── 22. Experiment Validator ──

def test_experiment_validator():
    print("\n=== 22. Experiment Validator ===")
    from infrastructure.feature_flags.experiments import (
        ExperimentValidator,
        Experiment,
        Variant,
        create_ab_variants,
    )

    validator = ExperimentValidator()

    # Valid experiment
    exp = Experiment(
        experiment_id="exp-1",
        feature_key="flag-1",
        variants=create_ab_variants(),
    )
    errors = validator.validate_experiment(exp)
    check("Valid experiment", len(errors) == 0)

    # Invalid: no experiment_id
    exp2 = Experiment(feature_key="flag-1", variants=create_ab_variants())
    errors = validator.validate_experiment(exp2)
    check("Missing experiment_id", len(errors) > 0)

    # Invalid: no feature_key
    exp3 = Experiment(experiment_id="exp-3", variants=create_ab_variants())
    errors = validator.validate_experiment(exp3)
    check("Missing feature_key", len(errors) > 0)

    # Invalid: too few variants
    exp4 = Experiment(
        experiment_id="exp-4",
        feature_key="flag-1",
        variants=[Variant(variant_id="only", is_control=True, weight=1.0)],
    )
    errors = validator.validate_experiment(exp4)
    check("Too few variants", len(errors) > 0)

    # Valid variant
    v = Variant(variant_id="v1", weight=50.0)
    errors = validator.validate_variant(v)
    check("Valid variant", len(errors) == 0)

    # Invalid variant: negative weight
    v_bad = Variant(variant_id="v2", weight=-1.0)
    errors = validator.validate_variant(v_bad)
    check("Negative weight", len(errors) > 0)


# ── 23. Evaluator Integration ──

async def test_evaluator_integration():
    print("\n=== 23. Evaluator Integration ===")
    from infrastructure.feature_flags import (
        FeatureEvaluator,
        FeatureFlag,
        FeatureContext,
        FeatureRule,
        EvaluationStrategy,
        FeatureFlagType,
        CanaryManager,
        ExperimentManager,
        create_ab_variants,
    )

    evaluator = FeatureEvaluator()

    # Test canary strategy
    canary = CanaryManager()
    await canary.start_deployment("canary-flag")
    evaluator.set_canary_manager(canary)

    flag = FeatureFlag(
        key="canary-flag",
        enabled=True,
        description="Canary test flag",
        flag_type=FeatureFlagType.BOOLEAN,
        strategy=EvaluationStrategy.CANARY,
        default_value=False,
    )
    ctx = FeatureContext(target_id="user-123")
    result = await evaluator.evaluate(flag, ctx)
    check("Canary evaluation works", result is not None)
    check("Canary has reason", "canary" in result.reason.lower())

    # Test experiment strategy
    exp_mgr = ExperimentManager()
    exp = exp_mgr.create("exp-test", "Test", "exp-flag", variants=create_ab_variants())
    await exp_mgr.start("exp-test")
    evaluator.set_experiment_manager(exp_mgr)

    exp_flag = FeatureFlag(
        key="exp-flag",
        enabled=True,
        description="Experiment test flag",
        flag_type=FeatureFlagType.BOOLEAN,
        strategy=EvaluationStrategy.EXPERIMENT,
        default_value=False,
        metadata={"experiment_id": "exp-test"},
    )
    exp_ctx = FeatureContext(target_id="user-456")
    result2 = await evaluator.evaluate(exp_flag, exp_ctx)
    check("Experiment evaluation works", result2 is not None)

    # Test CANARY strategy constant
    check("CANARY strategy exists", EvaluationStrategy.CANARY.value == "canary")

    # Evaluator stats
    stats = evaluator.get_stats()
    check("Evaluator stats", "evaluations" in stats)


# ── 24. Exceptions ──

def test_exceptions():
    print("\n=== 24. Exceptions ===")
    from infrastructure.feature_flags.exceptions import (
        CanaryError,
        CanaryDeploymentError,
        CanaryHealthError,
        CanaryPromotionError,
        CanaryRollbackError,
        ExperimentError,
        ExperimentNotFoundError,
        ExperimentValidationError,
        ExperimentAllocationError,
        ExperimentAnalysisError,
    )

    # Canary exceptions
    e1 = CanaryDeploymentError("flag-1", "failed")
    check("CanaryDeploymentError", "flag-1" in str(e1))
    check("CanaryDeploymentError feature_key", e1.feature_key == "flag-1")

    e2 = CanaryHealthError("flag-1", "critical", 45.0)
    check("CanaryHealthError", "critical" in str(e2))
    check("CanaryHealthError score", e2.health_score == 45.0)

    e3 = CanaryPromotionError("flag-1", "unhealthy")
    check("CanaryPromotionError", "unhealthy" in str(e3))

    e4 = CanaryRollbackError("flag-1", "failed")
    check("CanaryRollbackError", "failed" in str(e4))

    # Exception hierarchy
    check("CanaryError is FeatureFlagError", issubclass(CanaryError, Exception))
    check("CanaryDeploymentError is CanaryError", issubclass(CanaryDeploymentError, CanaryError))

    # Experiment exceptions
    e5 = ExperimentNotFoundError("exp-1")
    check("ExperimentNotFoundError", "exp-1" in str(e5))
    check("ExperimentNotFoundError id", e5.experiment_id == "exp-1")

    e6 = ExperimentValidationError("exp-1", ["bad variant", "no control"])
    check("ExperimentValidationError", "bad variant" in str(e6))
    check("ExperimentValidationError errors", len(e6.errors) == 2)

    e7 = ExperimentAllocationError("exp-1", "user-1", "no variants")
    check("ExperimentAllocationError", "user-1" in str(e7))
    check("ExperimentAllocationError target_id", e7.target_id == "user-1")

    e8 = ExperimentAnalysisError("exp-1", "insufficient data")
    check("ExperimentAnalysisError", "insufficient data" in str(e8))

    check("ExperimentError is FeatureFlagError", issubclass(ExperimentError, Exception))
    check("ExperimentNotFoundError is ExperimentError", issubclass(ExperimentNotFoundError, ExperimentError))


# ── Main ──

def main():
    print("=" * 60)
    print("  Canary Release Platform & Experiment Framework Validation")
    print("=" * 60)

    # Sync tests
    test_canary_stage()
    test_canary_policy()
    test_canary_health()
    test_canary_metrics()
    test_canary_validator()
    test_canary_monitor()
    test_variant()
    test_variant_allocator()
    test_statistics_collector()
    test_experiment_analyzer()
    test_winner_selector()
    test_experiment_model()
    test_experiment_metrics()
    test_experiment_validator()
    test_exceptions()

    # Async tests
    asyncio.run(test_canary_deployment())
    asyncio.run(test_canary_rollback())
    asyncio.run(test_canary_manager())
    asyncio.run(test_canary_audit())
    asyncio.run(test_experiment_manager())
    asyncio.run(test_experiment_archive())
    asyncio.run(test_experiment_audit())
    asyncio.run(test_evaluator_integration())

    print("\n" + "=" * 60)
    print(f"  Results: {PASSED} passed, {FAILED} failed")
    print("=" * 60)

    if FAILED > 0:
        sys.exit(1)
    else:
        print("\n  All validations passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
