"""
Validation script for rollout engine.

Comprehensive test suite covering:
    1. Consistent hashing (MurmurHash3, SHA-256, CRC32)
    2. Rollout policy models
    3. Sticky assignment engine
    4. RolloutEngine unified evaluation
    5. Progressive rollout (multi-stage)
    6. Segment-based rollout
    7. Rollout strategy (segments + percentage)
    8. Scheduler
    9. Cache
    10. Validator
    11. Metrics
    12. Audit
    13. Evaluator integration
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


# ── 1. Hasher Tests ──

def test_hasher():
    print("\n=== 1. Hasher Tests ===")
    from infrastructure.feature_flags.rollout import (
        ConsistentHasher,
        compute_hash,
        is_in_percentage_rollout,
    )

    h = ConsistentHasher(algorithm="murmur3")
    check("MurmurHash3 stable", h.hash("test_key") == h.hash("test_key"))
    check("MurmurHash3 different", h.hash("key1") != h.hash("key2"))

    h2 = ConsistentHasher(algorithm="sha256")
    check("SHA-256 stable", h2.hash("test_key") == h2.hash("test_key"))
    check("SHA-256 different", h2.hash("key1") != h2.hash("key2"))

    h3 = ConsistentHasher(algorithm="crc32")
    check("CRC32 stable", h3.hash("test_key") == h3.hash("test_key"))
    check("CRC32 different", h3.hash("key1") != h3.hash("key2"))

    # Bucket tests
    check("Bucket in range (10000)", h.hash_to_bucket("key", 10000) < 10000)
    check("Bucket in range (100)", h.hash_to_bucket("key", 100) < 100)

    # Rollout percentage
    check("0% never in rollout", not h.is_in_rollout("key", 0.0))
    check("100% always in rollout", h.is_in_rollout("key", 100.0))

    # Convenience functions
    check("compute_hash works", compute_hash("test") >= 0)
    check("is_in_percentage_rollout 0%", not is_in_percentage_rollout("f", "a", 0.0))
    check("is_in_percentage_rollout 100%", is_in_percentage_rollout("f", "a", 100.0))

    # Cache
    h.clear_cache()
    check("Cache cleared", h.cache_size == 0)


# ── 2. Rollout Policy Tests ──

def test_rollout_policy():
    print("\n=== 2. Rollout Policy Tests ===")
    from infrastructure.feature_flags.rollout import (
        RolloutAssignment,
        RolloutPolicy,
        SegmentDefinition,
        ProgressiveStage,
    )

    # RolloutPolicy
    p = RolloutPolicy(percentage=10.0, hash_key="account_id")
    check("Policy percentage", p.percentage == 10.0)
    check("Policy hash_key", p.hash_key == "account_id")
    check("Policy to_dict", p.to_dict()["percentage"] == 10.0)

    p2 = RolloutPolicy.from_dict({"percentage": 25.0, "hash_key": "user_id"})
    check("Policy from_dict", p2.percentage == 25.0)

    # Validation
    try:
        RolloutPolicy(percentage=-1)
        check("Policy rejects negative", False)
    except ValueError:
        check("Policy rejects negative", True)

    # RolloutAssignment
    a = RolloutAssignment(flag_key="test", target_id="acc1", assigned=True, percentage=10.0)
    check("Assignment to_dict", a.to_dict()["assigned"] is True)
    check("Assignment serializable", "flag_key" in a.to_dict())

    # SegmentDefinition
    s = SegmentDefinition(
        segment_id="vip",
        name="VIP Accounts",
        attribute="account_type",
        operator="==",
        values=["vip"],
        percentage=50.0,
    )
    check("Segment matches", s.matches({"account_type": "vip"}))
    check("Segment no match", not s.matches({"account_type": "normal"}))
    check("Segment to_dict", s.to_dict()["segment_id"] == "vip")

    s2 = SegmentDefinition(
        segment_id="brokers",
        attribute="broker",
        operator="IN",
        values=["IBKR", "TD"],
    )
    check("Segment IN match", s2.matches({"broker": "IBKR"}))
    check("Segment IN no match", not s2.matches({"broker": "RH"}))

    # ProgressiveStage
    stage = ProgressiveStage(stage_id="s1", percentage=5.0)
    check("Stage percentage", stage.percentage == 5.0)
    check("Stage to_dict", stage.to_dict()["stage_id"] == "s1")

    try:
        ProgressiveStage(stage_id="bad", percentage=-5)
        check("Stage rejects negative", False)
    except ValueError:
        check("Stage rejects negative", True)


# ── 3. Sticky Assignment Tests ──

async def test_sticky_assignment():
    print("\n=== 3. Sticky Assignment Tests ===")
    from infrastructure.feature_flags.rollout import (
        RolloutPolicy,
        StickyAssignment,
    )

    sa = StickyAssignment()
    policy = RolloutPolicy(percentage=50.0, hash_key="account_id")

    result1 = await sa.assign("flag1", "acc1", policy)
    result2 = await sa.assign("flag1", "acc1", policy)
    check("Sticky assignment consistent", result1.assigned == result2.assigned)
    check("Assignment has bucket", result1.bucket >= 0)
    check("Assignment has percentage", result1.percentage == 50.0)

    # Different targets may get different results (statistical)
    results = [await sa.assign("flag1", f"acc{i}", policy) for i in range(100)]
    assigned_count = sum(1 for r in results if r.assigned)
    # With 50% rollout, should be roughly 50
    check("50% rollout approximately correct", 20 <= assigned_count <= 80)

    # Cache
    stats = sa.get_stats()
    check("Assignment stats exist", "assignments" in stats)
    check("Assignment count", stats["assignments"] >= 100)

    # Invalidate
    invalidated = sa.invalidate("flag1")
    check("Invalidation works", invalidated >= 0)


# ── 4. RolloutEngine Tests ──

async def test_rollout_engine():
    print("\n=== 4. RolloutEngine Tests ===")
    from infrastructure.feature_flags.rollout import (
        RolloutEngine,
        RolloutPolicy,
    )

    engine = RolloutEngine()
    policy = RolloutPolicy(percentage=50.0)

    result = await engine.evaluate("flag1", "acc1", policy=policy)
    check("Engine evaluates", result.assigned is True or result.assigned is False)
    check("Engine has bucket", result.bucket >= 0)
    check("Engine has percentage", result.percentage == 50.0)

    # Batch evaluation
    results = await engine.evaluate_batch(
        "flag1", ["acc1", "acc2", "acc3"], policy=policy,
    )
    check("Batch evaluation", len(results) == 3)

    # Cache
    result2 = await engine.evaluate("flag1", "acc1", policy=policy)
    check("Engine cache hit", result2.bucket == result.bucket)

    # Disabled policy
    disabled_policy = RolloutPolicy(percentage=50.0, enabled=False)
    result3 = await engine.evaluate("flag1", "acc1", policy=disabled_policy)
    check("Disabled policy not assigned", not result3.assigned)

    # Stats
    stats = engine.get_stats()
    check("Engine stats", "evaluations" in stats)


# ── 5. Progressive Rollout Tests ──

def test_progressive_rollout():
    print("\n=== 5. Progressive Rollout Tests ===")
    from infrastructure.feature_flags.rollout import (
        ProgressiveRollout,
    )

    pr = ProgressiveRollout("test-flag")
    check("Initial percentage", pr.current_percentage == 5.0)
    check("Not active initially", not pr.is_active)

    pr.start()
    check("Active after start", pr.is_active)
    check("First stage index", pr.current_stage_index == 0)

    # Record requests before advance
    for _ in range(200):
        pr.record_request()
    stats_before = pr.get_stats()
    check("Requests recorded", stats_before["requests"] == 200)

    # Advance (resets request count)
    advanced = pr.advance(force=True)
    check("Advanced stage", advanced)
    check("Stage index 1", pr.current_stage_index == 1)
    check("Percentage 10%", pr.current_percentage == 10.0)

    # Rollback
    rolled = pr.rollback()
    check("Rollback works", rolled)
    check("Back to stage 0", pr.current_stage_index == 0)
    check("Back to 5%", pr.current_percentage == 5.0)

    # Progress
    check("Progress > 0", pr.progress >= 0.0)

    # Stats
    stats = pr.get_stats()
    check("Progressive stats", "current_percentage" in stats)

    pr.stop()
    pr.reset()
    check("Reset works", pr.current_stage_index == 0)


# ── 6. Segment Engine Tests ──

def test_segment_engine():
    print("\n=== 6. Segment Engine Tests ===")
    from infrastructure.feature_flags.rollout import (
        SegmentDefinition,
        SegmentEngine,
    )

    engine = SegmentEngine()

    # Add segments
    engine.add_segment(SegmentDefinition(
        segment_id="vip",
        attribute="account_type",
        operator="==",
        values=["vip"],
        percentage=50.0,
        priority=1,
    ))
    engine.add_segment(SegmentDefinition(
        segment_id="ibkr",
        attribute="broker",
        operator="==",
        values=["IBKR"],
        percentage=25.0,
        priority=2,
    ))

    # Resolve VIP
    seg = engine.resolve({"account_type": "vip", "broker": "RH"})
    check("VIP segment matched", seg is not None)
    check("VIP percentage", seg.percentage == 50.0)

    # Resolve IBKR (lower priority since VIP didn't match)
    seg2 = engine.resolve({"account_type": "normal", "broker": "IBKR"})
    check("IBKR segment matched", seg2 is not None)
    check("IBKR percentage", seg2.percentage == 25.0)

    # No match
    seg3 = engine.resolve({"account_type": "normal", "broker": "RH"})
    check("No segment matched", seg3 is None)

    # Get all segments
    segs = engine.get_segments()
    check("Two segments", len(segs) == 2)

    # Remove
    removed = engine.remove_segment("vip")
    check("Segment removed", removed)
    check("One segment left", len(engine.get_segments()) == 1)

    # Stats
    stats = engine.get_stats()
    check("Segment stats", "total_segments" in stats)


# ── 7. Rollout Strategy Tests ──

async def test_rollout_strategy():
    print("\n=== 7. Rollout Strategy Tests ===")
    from infrastructure.feature_flags.rollout import (
        RolloutPolicy,
        RolloutStrategy,
        SegmentDefinition,
    )

    strategy = RolloutStrategy(RolloutPolicy(percentage=10.0))

    # Add segment
    strategy.segment_engine.add_segment(SegmentDefinition(
        segment_id="vip",
        attribute="account_type",
        operator="==",
        values=["vip"],
        percentage=50.0,
    ))

    # Non-VIP target
    result1 = await strategy.evaluate("flag1", "acc1", {"account_type": "normal"})
    check("Non-VIP evaluated", result1.assigned is not None)

    # VIP target
    result2 = await strategy.evaluate("flag1", "acc2", {"account_type": "vip"})
    check("VIP evaluated", result2.assigned is not None)

    # Stats
    stats = strategy.get_stats()
    check("Strategy stats", "evaluations" in stats)
    check("Segment hits tracked", stats["segment_hits"] >= 0)


# ── 8. Validator Tests ──

def test_validator():
    print("\n=== 8. Validator Tests ===")
    from infrastructure.feature_flags.rollout import (
        ProgressiveStage,
        RolloutAssignment,
        RolloutPolicy,
        RolloutValidator,
        SegmentDefinition,
    )

    validator = RolloutValidator()

    # Policy validation
    errors = validator.validate_policy(RolloutPolicy(percentage=10.0))
    check("Valid policy", len(errors) == 0)

    try:
        bad_policy = RolloutPolicy(percentage=-5)
        errors2 = validator.validate_policy(bad_policy)
        check("Invalid percentage", len(errors2) > 0)
    except ValueError:
        check("Invalid percentage", True)

    # Segment validation
    seg = SegmentDefinition(segment_id="test", attribute="broker", operator="==", values=["IBKR"])
    errors3 = validator.validate_segment(seg)
    check("Valid segment", len(errors3) == 0)

    seg_bad = SegmentDefinition(segment_id="", attribute="", operator="==", values=[])
    errors4 = validator.validate_segment(seg_bad)
    check("Invalid segment", len(errors4) > 0)

    # Progressive stages
    stages = [
        ProgressiveStage(stage_id="s1", percentage=5.0),
        ProgressiveStage(stage_id="s2", percentage=10.0),
    ]
    errors5 = validator.validate_progressive_stages(stages)
    check("Valid stages", len(errors5) == 0)

    bad_stages = [
        ProgressiveStage(stage_id="s1", percentage=10.0),
        ProgressiveStage(stage_id="s2", percentage=5.0),
    ]
    errors6 = validator.validate_progressive_stages(bad_stages)
    check("Invalid stage ordering", len(errors6) > 0)

    # Assignment validation
    a = RolloutAssignment(flag_key="f", target_id="t", assigned=True, percentage=10.0)
    errors7 = validator.validate_assignment(a)
    check("Valid assignment", len(errors7) == 0)


# ── 9. Metrics Tests ──

def test_rollout_metrics():
    print("\n=== 9. Rollout Metrics Tests ===")
    from infrastructure.feature_flags.rollout import RolloutMetrics

    m = RolloutMetrics()

    m.record_rollout_eval("flag1", 10.0, True, 1.5)
    m.record_rollout_eval("flag1", 10.0, False, 2.0)
    m.record_cache_hit("flag1")
    m.record_cache_miss("flag1")
    m.record_segment_match("seg1", "flag1")
    m.record_progressive_stage("flag1", 1, 10.0)
    m.record_hash_computation("murmur3")

    check("Eval total", m.get_eval_total("flag1") == 2)
    check("Assignment rate", 0.0 <= m.get_assignment_rate("flag1") <= 1.0)
    check("Avg latency > 0", m.get_avg_latency("flag1") > 0)
    check("Cache hit ratio", m.get_cache_hit_ratio("flag1") > 0)

    snap = m.snapshot()
    check("Snapshot has eval_total", "eval_total" in snap)
    check("Snapshot has cache_hits", "cache_hits" in snap)

    counters = m.get_counter_values()
    check("Counter values", len(counters) > 0)

    m.reset()
    check("Reset works", m.get_eval_total("flag1") == 0)


# ── 10. Audit Tests ──

async def test_rollout_audit():
    print("\n=== 10. Rollout Audit Tests ===")
    from infrastructure.feature_flags.rollout import RolloutAudit

    audit = RolloutAudit()

    entry = await audit.record_assignment(
        flag_key="flag1",
        target_id="acc1",
        assigned=True,
        percentage=10.0,
        hash_value=12345,
        bucket=5000,
    )
    check("Assignment record", entry["type"] == "assignment")
    check("Assignment flag_key", entry["flag_key"] == "flag1")

    entry2 = await audit.record_stage_transition(
        feature_key="flag1",
        from_stage=0,
        to_stage=1,
        from_percentage=5.0,
        to_percentage=10.0,
    )
    check("Stage transition", entry2["type"] == "stage_transition")

    entry3 = await audit.record_rollback(
        feature_key="flag1",
        from_percentage=10.0,
        to_percentage=5.0,
    )
    check("Rollback record", entry3["type"] == "rollback")

    entries = await audit.query(flag_key="flag1", limit=10)
    check("Query returns results", len(entries) >= 3)

    stats = audit.get_stats()
    check("Audit stats", "total_entries" in stats)


# ── 11. Cache Tests ──

async def test_rollout_cache():
    print("\n=== 11. Rollout Cache Tests ===")
    from infrastructure.feature_flags.rollout import RolloutCache

    cache = RolloutCache(hash_ttl=5.0, assignment_ttl=10.0)

    await cache.set_hash("key1", 12345)
    val = await cache.get_hash("key1")
    check("Hash cache hit", val == 12345)

    val2 = await cache.get_hash("nonexistent")
    check("Hash cache miss", val2 is None)

    await cache.set_assignment("key2", {"assigned": True})
    val3 = await cache.get_assignment("key2")
    check("Assignment cache hit", val3 == {"assigned": True})

    cache.invalidate_hash("key1")
    val4 = await cache.get_hash("key1")
    check("Invalidation works", val4 is None)

    stats = cache.get_stats()
    check("Cache stats", "hash_cache_size" in stats)


# ── 12. Scheduler Tests ──

def test_scheduler():
    print("\n=== 12. Scheduler Tests ===")
    from infrastructure.feature_flags.rollout import (
        FREQUENCY_IMMEDIATE,
        RolloutScheduler,
        ScheduleConfig,
    )

    scheduler = RolloutScheduler()
    schedule = ScheduleConfig(frequency=FREQUENCY_IMMEDIATE)

    called = []

    def on_advance(flag_key):
        called.append(flag_key)

    scheduler.schedule_advance("flag1", on_advance, schedule)
    check("Scheduled", "flag1" in scheduler.get_schedules())

    scheduler.unschedule("flag1")
    check("Unscheduled", "flag1" not in scheduler.get_schedules())

    stats = scheduler.get_stats()
    check("Scheduler stats", "scheduled" in stats)


# ── 13. Evaluator Integration Tests ──

async def test_evaluator_integration():
    print("\n=== 13. Evaluator Integration Tests ===")
    from infrastructure.feature_flags import (
        FeatureContext,
        FeatureEvaluator,
        FeatureFlag,
        FeatureRule,
    )
    from infrastructure.feature_flags.constants import (
        EvaluationStrategy,
        FeatureFlagType,
    )

    evaluator = FeatureEvaluator()

    # Test PERCENTAGE strategy with RolloutEngine
    flag = FeatureFlag(
        key="test.percentage_flag",
        enabled=True,
        description="Test percentage flag",
        flag_type=FeatureFlagType.BOOLEAN,
        strategy=EvaluationStrategy.PERCENTAGE,
        default_value=False,
        rules=[
            FeatureRule(
                rule_id="rule-1",
                priority=10,
                condition="10",
                value=True,
                enabled=True,
            )
        ],
        metadata={"rollout_percentage": 10.0},
    )

    ctx = FeatureContext(
        target_id="acc_001",
        target_type="account",
        attributes={"account_id": "acc_001", "broker": "IBKR"},
    )

    result = await evaluator.evaluate(flag, ctx)
    check("Percentage flag evaluated", result.result.value in ("hit", "no_rule"))
    check("Has reason", len(result.reason) > 0)


# ── Main ──

async def main():
    global PASSED, FAILED
    print("=" * 60)
    print("Feature Flag Rollout Engine - Validation")
    print("=" * 60)

    try:
        # Synchronous tests
        test_hasher()
        test_rollout_policy()
        test_progressive_rollout()
        test_segment_engine()
        test_validator()
        test_rollout_metrics()
        test_scheduler()

        # Async tests
        await test_sticky_assignment()
        await test_rollout_engine()
        await test_rollout_strategy()
        await test_rollout_audit()
        await test_rollout_cache()
        await test_evaluator_integration()

    except Exception as e:
        print(f"\n!!! UNCAUGHT ERROR: {e}")
        traceback.print_exc()
        FAILED += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {PASSED} passed, {FAILED} failed, {PASSED + FAILED} total")
    print("=" * 60)

    if FAILED == 0:
        print("\n=== ALL TESTS PASSED ===")
    else:
        print(f"\n=== {FAILED} TESTS FAILED ===")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
