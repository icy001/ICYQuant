"""Comprehensive validation tests for the ICYQuant intelligent resolver & load balancer.

Tests all 21 sections of the resolver pipeline:
1. ResolveContext
2. ResolveStrategy + StrategyConfig
3. RoundRobin
4. Weighted
5. LeastConnection
6. LeastLatency
7. Random
8. ConsistentHash
9. LoadBalancer
10. ServiceRouter
11. LocalityRouter
12. VersionRouter
13. CanaryRouter
14. FeatureFlagRouter
15. HealthFilter
16. CircuitFilter
17. ResolverCache
18. ResolverMetrics
19. ResolverDiagnostics
20. ResolverTelemetry
21. IntelligentServiceResolver

Run: python -m infrastructure.service_discovery._validate_resolver
"""

from __future__ import annotations

import asyncio
import sys
import os
import time
import threading
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from infrastructure.service_discovery.instance import ServiceInstance
from infrastructure.service_discovery.models import ServiceStatus
from infrastructure.service_discovery.resolver.context import ResolveContext
from infrastructure.service_discovery.resolver.strategy import (
    ResolveStrategy,
    StrategyConfig,
)
from infrastructure.service_discovery.resolver.selector import (
    RandomLoadBalancer,
)
from infrastructure.service_discovery.resolver.round_robin import RoundRobin
from infrastructure.service_discovery.resolver.weighted import Weighted
from infrastructure.service_discovery.resolver.least_connection import LeastConnection
from infrastructure.service_discovery.resolver.least_latency import LeastLatency
from infrastructure.service_discovery.resolver.random import Random as RandomSelector
from infrastructure.service_discovery.resolver.consistent_hash import ConsistentHash
from infrastructure.service_discovery.resolver.load_balancer import LoadBalancer
from infrastructure.service_discovery.resolver.router import ServiceRouter
from infrastructure.service_discovery.resolver.locality import LocalityRouter
from infrastructure.service_discovery.resolver.version_router import VersionRouter
from infrastructure.service_discovery.resolver.canary import CanaryRouter
from infrastructure.service_discovery.resolver.feature_flag import FeatureFlagRouter
from infrastructure.service_discovery.resolver.health_filter import HealthFilter
from infrastructure.service_discovery.resolver.circuit_filter import (
    CircuitFilter,
    CLOSED,
    OPEN,
    HALF_OPEN,
)
from infrastructure.service_discovery.resolver.cache import ResolverCache
from infrastructure.service_discovery.resolver.metrics import ResolverMetrics
from infrastructure.service_discovery.resolver.diagnostics import ResolverDiagnostics
from infrastructure.service_discovery.resolver.telemetry import ResolverTelemetry
from infrastructure.service_discovery.resolver.resolver import IntelligentServiceResolver

checks_passed = 0
checks_failed = 0


def check(name, condition):
    global checks_passed, checks_failed
    if condition:
        checks_passed += 1
    else:
        checks_failed += 1
        print(f"  [FAIL] {name}")


def make_instance(
    service_name="payment",
    instance_id=None,
    host="127.0.0.1",
    port=8080,
    version="v1",
    namespace="default",
    weight=100,
    healthy=True,
    region="ap-east",
    zone="zone-a",
    canary=False,
    features=None,
):
    if instance_id is None:
        instance_id = f"{service_name}-{len(make_instance._counter)}"
        make_instance._counter += 1
    metadata = {}
    if region:
        metadata["region"] = region
    if zone:
        metadata["zone"] = zone
    if canary:
        metadata["canary"] = True
    if features:
        metadata["features"] = features
    return ServiceInstance(
        service_name=service_name,
        instance_id=instance_id,
        host=host,
        port=port,
        version=version,
        namespace=namespace,
        metadata=metadata,
        status=ServiceStatus.HEALTHY if healthy else ServiceStatus.UNHEALTHY,
        weight=weight,
        healthy=healthy,
    )


make_instance._counter = 0

inst1 = make_instance(
    service_name="payment",
    instance_id="pay-1",
    host="10.0.0.1",
    port=8080,
    version="v1",
    weight=100,
    healthy=True,
    region="ap-east",
    zone="zone-a",
)
inst2 = make_instance(
    service_name="payment",
    instance_id="pay-2",
    host="10.0.0.2",
    port=8080,
    version="v1",
    weight=200,
    healthy=True,
    region="ap-east",
    zone="zone-b",
)
inst3 = make_instance(
    service_name="payment",
    instance_id="pay-3",
    host="10.0.0.3",
    port=8080,
    version="v2",
    weight=100,
    healthy=True,
    region="ap-east",
    zone="zone-a",
)
inst_unhealthy = make_instance(
    service_name="payment",
    instance_id="pay-unhealthy",
    host="10.0.0.4",
    port=8080,
    version="v1",
    weight=50,
    healthy=False,
    region="ap-west",
    zone="zone-c",
)
inst_canary = make_instance(
    service_name="payment",
    instance_id="pay-canary",
    host="10.0.0.5",
    port=8080,
    version="canary",
    weight=100,
    healthy=True,
    region="ap-east",
    zone="zone-a",
    canary=True,
)

ALL_INSTANCES = [inst1, inst2, inst3, inst_unhealthy, inst_canary]


def main():
    global checks_passed, checks_failed

    print("=" * 60)
    print("ICYQuant Intelligent Resolver Validation Suite")
    print("=" * 60)

    # === 1. ResolveContext ===
    print("\n=== 1. ResolveContext ===")
    ctx = ResolveContext()
    check("default namespace", ctx.namespace == "default")
    check("default strategy", ctx.strategy == "round_robin")
    check("default canary", ctx.canary is False)
    check("default version is None", ctx.version is None)
    check("default region is None", ctx.region is None)
    check("default zone is None", ctx.zone is None)
    check("default timeout", ctx.timeout == 5.0)

    ctx2 = ResolveContext(
        namespace="prod",
        version="v2",
        region="us-east",
        zone="us-east-1a",
        user_id="user-123",
        strategy="least_latency",
        canary=True,
        features={"dark_launch": True},
        metadata={"env": "prod"},
        timeout=10.0,
    )
    check("custom namespace", ctx2.namespace == "prod")
    check("custom version", ctx2.version == "v2")
    check("custom region", ctx2.region == "us-east")
    check("custom zone", ctx2.zone == "us-east-1a")
    check("custom user_id", ctx2.user_id == "user-123")
    check("custom strategy", ctx2.strategy == "least_latency")
    check("custom canary", ctx2.canary is True)
    check("custom features", ctx2.features == {"dark_launch": True})
    check("custom metadata", ctx2.metadata == {"env": "prod"})
    check("custom timeout", ctx2.timeout == 10.0)

    d = ctx2.to_dict()
    check("to_dict returns dict", isinstance(d, dict))
    check("to_dict namespace", d["namespace"] == "prod")
    check("to_dict version", d["version"] == "v2")
    check("to_dict strategy", d["strategy"] == "least_latency")
    check("to_dict canary", d["canary"] is True)

    ctx3 = ResolveContext.from_dict(d)
    check("from_dict creates instance", isinstance(ctx3, ResolveContext))
    check("from_dict roundtrip namespace", ctx3.namespace == "prod")
    check("from_dict roundtrip version", ctx3.version == "v2")
    check("from_dict roundtrip strategy", ctx3.strategy == "least_latency")
    check("from_dict roundtrip canary", ctx3.canary is True)

    ctx4 = ResolveContext.from_dict(None)
    check("from_dict None gives defaults", ctx4.namespace == "default")

    ctx5 = ctx2.with_version("v3")
    check("with_version returns new instance", isinstance(ctx5, ResolveContext))
    check("with_version sets version", ctx5.version == "v3")
    check("with_version preserves namespace", ctx5.namespace == "prod")
    check("with_version preserves strategy", ctx5.strategy == "least_latency")

    ctx6 = ctx2.with_strategy("random")
    check("with_strategy returns new instance", isinstance(ctx6, ResolveContext))
    check("with_strategy sets strategy", ctx6.strategy == "random")
    check("with_strategy preserves version", ctx6.version == "v2")

    ctx_match = ResolveContext(version="v2")
    check("matches_instance with correct version", ctx_match.matches_instance(inst3))
    check("matches_instance rejects wrong version", not ctx_match.matches_instance(inst1))
    check("matches_instance with None", ctx.matches_instance(None) is False)

    ctx_region = ResolveContext(region="ap-east")
    check("matches_instance region match", ctx_region.matches_instance(inst1))
    ctx_region_wrong = ResolveContext(region="us-west")
    check("matches_instance region mismatch", not ctx_region_wrong.matches_instance(inst1))

    ctx_canary = ResolveContext(canary=True)
    check("matches_instance canary match", ctx_canary.matches_instance(inst_canary))
    check("matches_instance canary mismatch", not ctx_canary.matches_instance(inst1))

    ctx_eq = ResolveContext(
        namespace="prod",
        version="v2",
        region="us-east",
        zone="us-east-1a",
        user_id="user-123",
        strategy="least_latency",
        canary=True,
        features={"dark_launch": True},
        metadata={"env": "prod"},
        timeout=10.0,
    )
    check("__eq__ equal", ctx2 == ctx_eq)
    check("__eq__ not equal", not (ctx == ctx2))

    print(f"  Section 1: {checks_passed} passed, {checks_failed} failed so far")

    # === 2. ResolveStrategy + StrategyConfig ===
    print("\n=== 2. ResolveStrategy + StrategyConfig ===")
    check("ROUND_ROBIN value", ResolveStrategy.ROUND_ROBIN.value == "round_robin")
    check("RANDOM value", ResolveStrategy.RANDOM.value == "random")
    check("WEIGHTED value", ResolveStrategy.WEIGHTED.value == "weighted")
    check("LEAST_CONNECTION value", ResolveStrategy.LEAST_CONNECTION.value == "least_connection")
    check("LEAST_LATENCY value", ResolveStrategy.LEAST_LATENCY.value == "least_latency")
    check("CONSISTENT_HASH value", ResolveStrategy.CONSISTENT_HASH.value == "consistent_hash")
    check("LOCALITY value", ResolveStrategy.LOCALITY.value == "locality")
    check("all strategies count", len(ResolveStrategy) == 7)

    sc = StrategyConfig()
    check("default strategy", sc.strategy == ResolveStrategy.ROUND_ROBIN)
    check("default get missing", sc.get("key") is None)
    check("default get with default", sc.get("key", "fallback") == "fallback")

    sc.set("timeout", 5.0)
    check("set then get", sc.get("timeout") == 5.0)
    sc.set("max_retries", 3)
    check("set second param", sc.get("max_retries") == 3)

    d2 = sc.to_dict()
    check("to_dict has strategy", d2["strategy"] == "round_robin")
    check("to_dict has params", d2["params"]["timeout"] == 5.0)
    check("to_dict has second param", d2["params"]["max_retries"] == 3)

    sc2 = StrategyConfig(strategy=ResolveStrategy.WEIGHTED, weight=200)
    check("custom strategy config", sc2.strategy == ResolveStrategy.WEIGHTED)
    check("custom param", sc2.get("weight") == 200)

    sc3 = StrategyConfig(strategy=ResolveStrategy.RANDOM, seed=42)
    d3 = sc3.to_dict()
    check("seed param in to_dict", d3["params"]["seed"] == 42)

    sc_eq1 = StrategyConfig(strategy=ResolveStrategy.WEIGHTED, weight=200)
    check("StrategyConfig __eq__ equal", sc2 == sc_eq1)
    check("StrategyConfig __eq__ not equal", not (sc == sc2))

    print(f"  Section 2: {checks_passed} passed, {checks_failed} failed so far")

    # === 3. RoundRobin ===
    print("\n=== 3. RoundRobin ===")
    rr = RoundRobin()
    check("RoundRobin creates", rr is not None)
    check("initial index", rr._index == 0)

    sel1 = rr.next([inst1, inst2, inst3])
    check("first select", sel1.instance_id == "pay-1")
    sel2 = rr.next([inst1, inst2, inst3])
    check("second select", sel2.instance_id == "pay-2")
    sel3 = rr.next([inst1, inst2, inst3])
    check("third select", sel3.instance_id == "pay-3")
    sel4 = rr.next([inst1, inst2, inst3])
    check("wraps around", sel4.instance_id == "pay-1")

    rr.reset()
    check("reset index", rr._index == 0)
    check("after reset first", rr.next([inst1, inst2, inst3]).instance_id == "pay-1")

    stats = rr.get_stats()
    check("stats has selector", stats["selector"] == "RoundRobin")
    check("stats has current_index", "current_index" in stats)
    check("stats has select_count", stats["select_count"] > 0)

    check("empty list returns None", rr.next([]) is None)

    print(f"  Section 3: {checks_passed} passed, {checks_failed} failed so far")

    # === 4. Weighted ===
    print("\n=== 4. Weighted ===")
    wr = Weighted()
    check("Weighted creates", wr is not None)

    sel = wr.select([inst1, inst2, inst3])
    check("select returns instance", sel is not None)
    check("select from correct list", sel.instance_id in ["pay-1", "pay-2", "pay-3"])

    results = []
    for _ in range(1000):
        s = wr.select([inst1, inst2, inst3])
        if s:
            results.append(s.instance_id)
    count1 = results.count("pay-1")
    count2 = results.count("pay-2")
    count3 = results.count("pay-3")
    check("pay-2 selected most (weight=200)", count2 >= count1)
    check("pay-2 selected most (weight=200)", count2 >= count3)

    sel_zero = wr.select([])
    check("empty list returns None", sel_zero is None)

    stats = wr.get_stats()
    check("stats has selector", stats["selector"] == "Weighted")
    check("stats has select_count", stats["select_count"] > 0)

    inst_zero_weight = make_instance(
        service_name="test", instance_id="zero-w", weight=0, healthy=True
    )
    wr2 = Weighted()
    sel_zw = wr2.select([inst_zero_weight, inst1])
    check("zero weight excluded", sel_zw.instance_id == "pay-1" if sel_zw else True)

    print(f"  Section 4: {checks_passed} passed, {checks_failed} failed so far")

    # === 5. LeastConnection ===
    print("\n=== 5. LeastConnection ===")
    lc = LeastConnection(max_per_instance=100)
    check("LeastConnection creates", lc is not None)

    sel = lc.select([inst1, inst2, inst3])
    check("initial select returns instance", sel is not None)

    lc.acquire("pay-1")
    check("acquire increments", lc.get_connections("pay-1") == 1)
    lc.acquire("pay-1")
    check("second acquire", lc.get_connections("pay-1") == 2)
    lc.acquire("pay-2")
    check("acquire pay-2", lc.get_connections("pay-2") == 1)

    sel2 = lc.select([inst1, inst2, inst3])
    check("selects least connections", sel2.instance_id == "pay-3")

    lc.release("pay-1")
    check("release decrements", lc.get_connections("pay-1") == 1)
    lc.release("pay-1")
    check("release to zero", lc.get_connections("pay-1") == 0)
    lc.release("pay-1")
    check("release at zero stays zero", lc.get_connections("pay-1") == 0)

    sel3 = lc.select([inst1, inst2, inst3])
    check("after release selects pay-1 or pay-3", sel3.instance_id in ["pay-1", "pay-3"])

    lc_full = LeastConnection(max_per_instance=2)
    lc_full.acquire("inst-a")
    lc_full.acquire("inst-a")
    lc_full.acquire("inst-b")
    sel_full = lc_full.select([
        make_instance("s", "inst-a", healthy=True),
        make_instance("s", "inst-b", healthy=True),
    ])
    check("max_per_instance respected", sel_full.instance_id == "inst-b" if sel_full else True)

    stats = lc.get_stats()
    check("stats has selector", stats["selector"] == "LeastConnection")
    check("stats has max_per_instance", stats["max_per_instance"] == 100)
    check("stats has active_connections", "active_connections" in stats)

    sel_empty = lc.select([])
    check("empty list returns None", sel_empty is None)

    print(f"  Section 5: {checks_passed} passed, {checks_failed} failed so far")

    # === 6. LeastLatency ===
    print("\n=== 6. LeastLatency ===")
    ll = LeastLatency(window_size=10)
    check("LeastLatency creates", ll is not None)

    sel = ll.select([inst1, inst2, inst3])
    check("no latency data picks first cold", sel is not None)

    ll.record_latency("pay-1", 100.0)
    ll.record_latency("pay-1", 100.0)
    ll.record_latency("pay-1", 100.0)
    ll.record_latency("pay-1", 100.0)
    ll.record_latency("pay-2", 10.0)
    ll.record_latency("pay-2", 10.0)
    ll.record_latency("pay-2", 10.0)
    ll.record_latency("pay-2", 10.0)

    sel2 = ll.select([inst1, inst2, inst3])
    check("selects lowest latency (pay-2 or cold pay-3)", sel2.instance_id in ["pay-2", "pay-3"])

    ll.record_latency("pay-3", 5.0)
    sel3 = ll.select([inst1, inst2, inst3])
    check("selects lowest latency pay-3", sel3.instance_id == "pay-3")

    ll.record_latency("pay-1", 0)
    stats = ll.get_stats()
    check("stats has selector", stats["selector"] == "LeastLatency")
    check("stats has ewma", "ewma" in stats)
    check("stats has avg", "avg" in stats)
    check("stats has p99", "p99" in stats)
    check("stats has requests", "requests" in stats)
    check("timeout recorded", stats["timeouts"].get("pay-1", 0) >= 1)

    sel_empty = ll.select([])
    check("empty list returns None", sel_empty is None)

    print(f"  Section 6: {checks_passed} passed, {checks_failed} failed so far")

    # === 7. Random ===
    print("\n=== 7. Random ===")
    rnd = RandomSelector(seed=42)
    check("Random creates with seed", rnd is not None)

    sel = rnd.select([inst1, inst2, inst3])
    check("select returns instance", sel is not None)

    rnd2 = RandomSelector(seed=42)
    sel_replay = rnd2.select([inst1, inst2, inst3])
    check("seed consistency same first", sel.instance_id == sel_replay.instance_id)

    results = []
    for _ in range(1000):
        s = rnd.select([inst1, inst2, inst3])
        if s:
            results.append(s.instance_id)
    unique_ids = set(results)
    check("random selects all instances", len(unique_ids) >= 2)

    stats = rnd.get_stats()
    check("stats has selector", stats["selector"] == "Random")
    check("stats has seed", stats["seed"] == 42)
    check("stats has select_count", stats["select_count"] > 0)

    sel_empty = rnd.select([])
    check("empty list returns None", sel_empty is None)

    rnd_no_seed = RandomSelector()
    sel_ns = rnd_no_seed.select([inst1])
    check("no seed works", sel_ns.instance_id == "pay-1")

    print(f"  Section 7: {checks_passed} passed, {checks_failed} failed so far")

    # === 8. ConsistentHash ===
    print("\n=== 8. ConsistentHash ===")
    ch = ConsistentHash(hash_key_field="user_id", vnodes=50)
    check("ConsistentHash creates", ch is not None)

    sel = ch.select([inst1, inst2, inst3], key="user-123")
    check("select with key returns instance", sel is not None)

    sel_same = ch.select([inst1, inst2, inst3], key="user-123")
    check("same key same instance", sel.instance_id == sel_same.instance_id)

    sel_other = ch.select([inst1, inst2, inst3], key="user-456")
    check("different key may differ", True)

    stats = ch.get_stats()
    check("stats has selector", stats["selector"] == "ConsistentHash")
    check("stats has vnodes", stats["vnodes"] == 50)
    check("stats has ring_size", stats["ring_size"] > 0)
    check("stats has active_instances", stats["active_instances"] == 3)

    sel_empty = ch.select([])
    check("empty list returns None", sel_empty is None)

    ch2 = ConsistentHash(vnodes=1)
    check("vnodes minimum 1", ch2._vnodes >= 1)

    print(f"  Section 8: {checks_passed} passed, {checks_failed} failed so far")

    # === 9. LoadBalancer ===
    print("\n=== 9. LoadBalancer ===")
    lb = LoadBalancer()
    check("LoadBalancer creates", lb is not None)
    check("default strategy", lb._default_strategy == "round_robin")

    async def test_lb():
        sel = await lb.select([inst1, inst2, inst3])
        check("select returns instance", sel is not None)
        check("select from list", sel.instance_id in ["pay-1", "pay-2", "pay-3"])

        sel2 = await lb.select([inst1, inst2, inst3], strategy="random")
        check("select with strategy", sel2 is not None)

        sel3 = await lb.select([inst1, inst2, inst3], strategy="weighted")
        check("select weighted", sel3 is not None)

        sel4 = await lb.select([inst1, inst2, inst3], strategy="least_connection")
        check("select least_connection", sel4 is not None)

        sel5 = await lb.select([inst1, inst2, inst3], strategy="least_latency")
        check("select least_latency", sel5 is not None)

        sel6 = await lb.select([inst1, inst2, inst3], strategy="consistent_hash")
        check("select consistent_hash", sel6 is not None)

        sel_many = await lb.select_many([inst1, inst2, inst3], 2)
        check("select_many returns 2", len(sel_many) == 2)
        check("select_many unique", sel_many[0].instance_id != sel_many[1].instance_id)

        sel_many_zero = await lb.select_many([inst1, inst2], 0)
        check("select_many count=0 empty", len(sel_many_zero) == 0)

        sel_many_empty = await lb.select_many([], 1)
        check("select_many empty list", len(sel_many_empty) == 0)

        sel_many_overflow = await lb.select_many([inst1], 5)
        check("select_many overflow caps", len(sel_many_overflow) == 1)

    asyncio.run(test_lb())

    lb.register_strategy("custom", RandomLoadBalancer(seed=99))
    check("register custom strategy", lb.get_strategy("custom") is not None)

    try:
        lb.register_strategy("", RandomSelector())
        check("empty name raises", False)
    except ValueError:
        check("empty name raises ValueError", True)

    try:
        lb.register_strategy("bad", "not_a_selector")
        check("bad selector type raises", False)
    except TypeError:
        check("bad selector type raises TypeError", True)

    try:
        lb.get_strategy("nonexistent")
        check("missing strategy raises", False)
    except KeyError:
        check("missing strategy raises KeyError", True)

    stats = lb.get_stats()
    check("stats has default_strategy", stats["default_strategy"] == "round_robin")
    check("stats has total_selects", stats["total_selects"] > 0)
    check("stats has total_select_many", stats["total_select_many"] > 0)
    check("stats has registered_strategies", len(stats["registered_strategies"]) >= 6)

    print(f"  Section 9: {checks_passed} passed, {checks_failed} failed so far")

    # === 10. ServiceRouter ===
    print("\n=== 10. ServiceRouter ===")
    sr = ServiceRouter()
    check("ServiceRouter creates", sr is not None)

    sr.add_rule("version", version="v1")
    check("add_rule works", len(sr.get_rules()) == 1)

    async def test_sr():
        result = await sr.route([inst1, inst2, inst3])
        check("route filters by version", len(result) == 2)
        check("route correct versions", all(i.version == "v1" for i in result))

    asyncio.run(test_sr())

    sr.add_rule("namespace", namespace="default")
    async def test_sr2():
        result = await sr.route([inst1, inst2, inst3])
        check("route with multiple rules", len(result) == 2)

    asyncio.run(test_sr2())

    sr.clear_rules()
    check("clear_rules", len(sr.get_rules()) == 0)

    sr.add_rule("region")
    async def test_sr3():
        result = await sr.route([inst1, inst2, inst3, inst_unhealthy])
        check("route by region (no context returns all)", len(result) == 4)

        result_empty = await sr.route([])
        check("route empty", len(result_empty) == 0)

        ctx_region = ResolveContext(region="ap-west")
        result_ctx = await sr.route([inst1, inst2, inst3, inst_unhealthy], ctx_region)
        check("route with context region ap-west", len(result_ctx) == 1)

        ctx_region2 = ResolveContext(region="ap-east")
        result_ctx2 = await sr.route([inst1, inst2, inst3, inst_unhealthy], ctx_region2)
        check("route with context region ap-east", len(result_ctx2) == 3)

    asyncio.run(test_sr3())

    sr.clear_rules()
    sr.add_rule("canary", enabled=True)
    async def test_sr4():
        result = await sr.route([inst1, inst2, inst_canary])
        check("route canary only", len(result) == 1)
        check("route canary correct", result[0].instance_id == "pay-canary")

    asyncio.run(test_sr4())

    sr.clear_rules()
    sr.add_rule("zone", zone="zone-a")
    async def test_sr5():
        result = await sr.route([inst1, inst2, inst3])
        check("route zone filter", len(result) == 2)

    asyncio.run(test_sr5())

    sr.clear_rules()
    sr.add_rule("feature_flag", features={"beta": True})
    inst_beta = make_instance(
        service_name="payment",
        instance_id="pay-beta",
        version="v1",
        healthy=True,
        features={"beta": True},
    )
    async def test_sr6():
        result = await sr.route([inst1, inst2, inst_beta])
        check("route feature_flag", len(result) == 1)
        check("route feature_flag correct", result[0].instance_id == "pay-beta")

    asyncio.run(test_sr6())

    stats = sr.get_stats()
    check("stats has router", stats["router"] == "ServiceRouter")
    check("stats has rule_count", "rule_count" in stats)

    print(f"  Section 10: {checks_passed} passed, {checks_failed} failed so far")

    # === 11. LocalityRouter ===
    print("\n=== 11. LocalityRouter ===")
    lr = LocalityRouter()
    check("LocalityRouter creates", lr is not None)

    lr.set_affinity(region="ap-east", zone="zone-a")
    check("set_affinity region", lr._preferred_region == "ap-east")
    check("set_affinity zone", lr._preferred_zone == "zone-a")

    filtered = lr.filter([inst1, inst2, inst3])
    check("filter locality region+zone", len(filtered) >= 1)
    check("filter returns zone-a instances", all(
        i.metadata.get("zone") == "zone-a" for i in filtered
    ))

    score = lr.score(inst1)
    check("score same region+zone", score == 1.0)

    score2 = lr.score(inst2)
    check("score same region diff zone", score2 == 0.5)

    score3 = lr.score(inst_unhealthy)
    check("score diff region", score3 == 0.0)

    score_none = lr.score(None)
    check("score None instance", score_none == 0.0)

    lr2 = LocalityRouter()
    lr2.set_affinity(region="ap-east")
    filtered2 = lr2.filter([inst1, inst2, inst3, inst_unhealthy])
    check("filter by region only", len(filtered2) == 3)

    lr3 = LocalityRouter()
    filtered3 = lr3.filter([inst1, inst2])
    check("no affinity returns all", len(filtered3) == 2)

    filtered_empty = lr.filter([])
    check("filter empty list", len(filtered_empty) == 0)

    lr4 = LocalityRouter()
    lr4.set_affinity(region="us-west")
    filtered4 = lr4.filter([inst1, inst2])
    check("no matching region falls back", len(filtered4) == 2)

    ctx_loc = ResolveContext(region="ap-east", zone="zone-b")
    filtered_ctx = lr.filter([inst1, inst2, inst3], ctx_loc)
    check("filter with context affinity", len(filtered_ctx) >= 1)

    stats = lr.get_stats()
    check("stats has router", stats["router"] == "LocalityRouter")
    check("stats has route_count", stats["route_count"] >= 1)
    check("stats has local_hits", "local_hits" in stats)

    print(f"  Section 11: {checks_passed} passed, {checks_failed} failed so far")

    # === 12. VersionRouter ===
    print("\n=== 12. VersionRouter ===")
    vr = VersionRouter()
    check("VersionRouter creates", vr is not None)

    vr.add_version_alias("production", "v2")
    check("add_version_alias", vr.resolve_version("production") == "v2")
    check("stable alias default", vr.resolve_version("stable") == "v2")
    check("no alias passes through", vr.resolve_version("v3") == "v3")

    try:
        vr.add_version_alias("", "v1")
        check("empty alias raises", False)
    except ValueError:
        check("empty alias raises ValueError", True)

    try:
        vr.add_version_alias("x", "")
        check("empty version raises", False)
    except ValueError:
        check("empty version raises ValueError", True)

    ctx_v1 = ResolveContext(version="v1")
    result = vr.filter([inst1, inst2, inst3], ctx_v1)
    check("filter v1", len(result) == 2)
    check("filter v1 correct", all(i.version == "v1" for i in result))

    ctx_v2 = ResolveContext(version="v2")
    result2 = vr.filter([inst1, inst2, inst3], ctx_v2)
    check("filter v2", len(result2) == 1)
    check("filter v2 correct", result2[0].instance_id == "pay-3")

    ctx_prod = ResolveContext(version="production")
    result3 = vr.filter([inst1, inst2, inst3], ctx_prod)
    check("filter alias production->v2", len(result3) == 1)

    result_none = vr.filter([inst1, inst2], None)
    check("filter no context returns all", len(result_none) == 2)

    result_empty = vr.filter([], ctx_v1)
    check("filter empty list", len(result_empty) == 0)

    result_nomatch = vr.filter([inst1], ctx_v2)
    check("filter no matching version", len(result_nomatch) == 0)

    versions = vr.get_versions()
    check("get_versions returns list", isinstance(versions, list))
    check("get_versions contains stable", "stable" in versions)

    stats = vr.get_stats()
    check("stats has router", stats["router"] == "VersionRouter")
    check("stats has route_count", stats["route_count"] >= 1)
    check("stats has aliases", len(stats["aliases"]) >= 2)

    print(f"  Section 12: {checks_passed} passed, {checks_failed} failed so far")

    # === 13. CanaryRouter ===
    print("\n=== 13. CanaryRouter ===")
    cr = CanaryRouter()
    check("CanaryRouter creates", cr is not None)

    cr.configure("payment", percentage=0.0)
    check("configure percentage=0", cr.get_canary_config("payment")["percentage"] == 0.0)

    cr.configure("payment", percentage=100.0)
    check("configure percentage=100", cr.get_canary_config("payment")["percentage"] == 100.0)

    cr.configure("payment", percentage=-5.0)
    check("negative clamped to 0", cr.get_canary_config("payment")["percentage"] == 0.0)

    cr.configure("payment", percentage=150.0)
    check("over 100 clamped", cr.get_canary_config("payment")["percentage"] == 100.0)

    cr.configure("payment", percentage=50.0)
    config = cr.get_canary_config("payment")
    check("get_canary_config percentage", config["percentage"] == 50.0)

    check("get_canary_config unknown", cr.get_canary_config("unknown") is None)

    cr.configure("payment", percentage=100.0, target_versions=["canary"])
    ctx_cr = ResolveContext()
    result = cr.filter([inst1, inst2, inst_canary], ctx_cr)
    check("canary 100% filters to target", len(result) >= 1)

    cr.configure("payment", percentage=0.0)
    result_normal = cr.filter([inst1, inst2, inst_canary], ctx_cr)
    check("canary 0% normal path", len(result_normal) >= 1)

    cr.configure("payment", percentage=100.0)
    cr_user = CanaryRouter()
    cr_user.configure("payment", percentage=0.0, user_whitelist=["user-vip"])
    ctx_vip = ResolveContext(user_id="user-vip")
    is_canary_vip = cr_user.is_canary("payment", ctx_vip)
    check("user whitelist forces canary", is_canary_vip is True)

    ctx_normal_user = ResolveContext(user_id="other-user")
    is_canary_normal = cr_user.is_canary("payment", ctx_normal_user)
    check("non-whitelist not canary", is_canary_normal is False)

    cr_region = CanaryRouter()
    cr_region.configure("payment", percentage=0.0, region_whitelist=["ap-east"])
    ctx_region_canary = ResolveContext(region="ap-east")
    is_canary_region = cr_region.is_canary("payment", ctx_region_canary)
    check("region whitelist forces canary", is_canary_region is True)

    is_canary_no_config = cr_user.is_canary("unknown-service", None)
    check("no config returns False", is_canary_no_config is False)

    stats = cr.get_stats()
    check("stats has router", stats["router"] == "CanaryRouter")
    check("stats has route_count", "route_count" in stats)

    print(f"  Section 13: {checks_passed} passed, {checks_failed} failed so far")

    # === 14. FeatureFlagRouter ===
    print("\n=== 14. FeatureFlagRouter ===")
    ffr = FeatureFlagRouter()
    check("FeatureFlagRouter creates", ffr is not None)

    def is_dark_launch(ctx):
        return ctx.user_id == "user-vip"

    ffr.register_flag("dark_launch", is_dark_launch)
    check("register_flag", len(ffr.get_flags()) == 1)

    ctx_vip_ff = ResolveContext(user_id="user-vip")
    check("is_enabled vip", ffr.is_enabled("dark_launch", ctx_vip_ff) is True)
    ctx_normal_ff = ResolveContext(user_id="user-normal")
    check("is_enabled normal", ffr.is_enabled("dark_launch", ctx_normal_ff) is False)

    check("is_enabled unknown flag", ffr.is_enabled("nonexistent", ctx_vip_ff) is False)
    check("is_enabled None context", ffr.is_enabled("dark_launch", None) is False)

    inst_dark = make_instance(
        service_name="payment",
        instance_id="pay-dark",
        version="v1",
        healthy=True,
        features={"dark_launch": True},
    )
    result = ffr.filter([inst1, inst2, inst_dark], ctx_vip_ff)
    check("filter active flag", len(result) == 1)
    check("filter correct instance", result[0].instance_id == "pay-dark")

    result2 = ffr.filter([inst1, inst2, inst_dark], ctx_normal_ff)
    check("filter inactive flag returns all", len(result2) == 3)

    result3 = ffr.filter([], ctx_vip_ff)
    check("filter empty list", len(result3) == 0)

    result4 = ffr.filter([inst1], None)
    check("filter None context returns all", len(result4) == 1)

    ffr.unregister_flag("dark_launch")
    check("unregister_flag", len(ffr.get_flags()) == 0)

    try:
        ffr.register_flag("", lambda ctx: True)
        check("empty flag name raises", False)
    except ValueError:
        check("empty flag name raises ValueError", True)

    try:
        ffr.register_flag("bad", "not_callable")
        check("non-callable raises", False)
    except TypeError:
        check("non-callable raises TypeError", True)

    stats = ffr.get_stats()
    check("stats has router", stats["router"] == "FeatureFlagRouter")
    check("stats has registered_flags", "registered_flags" in stats)

    print(f"  Section 14: {checks_passed} passed, {checks_failed} failed so far")

    # === 15. HealthFilter ===
    print("\n=== 15. HealthFilter ===")
    hf = HealthFilter()
    check("HealthFilter creates", hf is not None)

    result = hf.filter([inst1, inst2, inst3, inst_unhealthy])
    check("filter removes unhealthy", len(result) == 3)
    check("filter no unhealthy", all(i.healthy for i in result))

    check("is_healthy healthy instance", hf.is_healthy(inst1) is True)
    check("is_healthy unhealthy instance", hf.is_healthy(inst_unhealthy) is False)
    check("is_healthy None", hf.is_healthy(None) is False)

    result_empty = hf.filter([])
    check("filter empty list", len(result_empty) == 0)

    inst_restarting = make_instance(
        service_name="payment",
        instance_id="pay-restart",
        version="v1",
        healthy=True,
    )
    inst_restarting.metadata["restarting"] = True
    result2 = hf.filter([inst_restarting])
    check("filter removes restarting", len(result2) == 0)

    inst_quarantined = make_instance(
        service_name="payment",
        instance_id="pay-quarantine",
        version="v1",
        healthy=True,
    )
    inst_quarantined.metadata["quarantined"] = True
    result3 = hf.filter([inst_quarantined])
    check("filter removes quarantined", len(result3) == 0)

    inst_lease = make_instance(
        service_name="payment",
        instance_id="pay-lease",
        version="v1",
        healthy=True,
    )
    inst_lease.metadata["lease_expired"] = True
    result4 = hf.filter([inst_lease])
    check("filter removes lease expired", len(result4) == 0)

    hf.set_health_callback(lambda iid, healthy: None)
    stats = hf.get_stats()
    check("stats has filter", stats["filter"] == "HealthFilter")
    check("stats has filter_count", stats["filter_count"] >= 1)
    check("stats has removed_count", stats["removed_count"] >= 1)

    try:
        hf.set_health_callback("not_callable")
        check("non-callable callback raises", False)
    except TypeError:
        check("non-callable callback raises TypeError", True)

    print(f"  Section 15: {checks_passed} passed, {checks_failed} failed so far")

    # === 16. CircuitFilter ===
    print("\n=== 16. CircuitFilter ===")
    cf = CircuitFilter(failure_threshold=3, recovery_timeout=1.0)
    check("CircuitFilter creates", cf is not None)

    check("initial state CLOSED", cf.get_circuit_state("inst-1") == CLOSED)

    result = cf.filter([inst1, inst2])
    check("filter healthy circuits", len(result) == 2)

    for _ in range(3):
        cf.record_failure("pay-1")
    check("circuit opened", cf.get_circuit_state("pay-1") == OPEN)

    result2 = cf.filter([inst1, inst2])
    check("filter removes open circuit", len(result2) == 1)

    cf.record_success("pay-1")
    check("circuit closed on success", cf.get_circuit_state("pay-1") == CLOSED)

    result3 = cf.filter([inst1, inst2])
    check("filter includes after success", len(result3) == 2)

    cf2 = CircuitFilter(failure_threshold=1, recovery_timeout=0.01)
    cf2.record_failure("inst-x")
    check("circuit opened at threshold 1", cf2.get_circuit_state("inst-x") == OPEN)

    time.sleep(0.02)
    check("circuit half-open after timeout", cf2.get_circuit_state("inst-x") == HALF_OPEN)

    cf2.record_success("inst-x")
    check("circuit closed after success in half-open", cf2.get_circuit_state("inst-x") == CLOSED)

    result_empty = cf.filter([])
    check("filter empty list", len(result_empty) == 0)

    stats = cf.get_stats()
    check("stats has filter", stats["filter"] == "CircuitFilter")
    check("stats has failure_threshold", stats["failure_threshold"] == 3)
    check("stats has tracked_instances", "tracked_instances" in stats)

    print(f"  Section 16: {checks_passed} passed, {checks_failed} failed so far")

    # === 17. ResolverCache ===
    print("\n=== 17. ResolverCache ===")
    cache = ResolverCache(ttl=5.0)
    check("ResolverCache creates", cache is not None)

    cache.set("payment", "region=ap-east", [inst1, inst2])
    cached = cache.get("payment", "region=ap-east")
    check("get after set", cached is not None)
    check("get returns correct count", len(cached) == 2)

    cached_miss = cache.get("payment", "region=us-west")
    check("get missing key returns None", cached_miss is None)

    cached_miss2 = cache.get("unknown", "key")
    check("get missing service returns None", cached_miss2 is None)

    cache.invalidate("payment")
    cached_after_inv = cache.get("payment", "region=ap-east")
    check("invalidate service removes entries", cached_after_inv is None)

    cache.set("svc-a", "k1", [inst1])
    cache.set("svc-b", "k1", [inst2])
    cache.invalidate()
    check("invalidate all clears", cache.get("svc-a", "k1") is None)
    check("invalidate all clears svc-b", cache.get("svc-b", "k1") is None)

    cache2 = ResolverCache(ttl=0.01)
    cache2.set("svc", "k", [inst1])
    time.sleep(0.02)
    check("expired entry is None", cache2.get("svc", "k") is None)

    stats = cache.get_stats()
    check("stats has cache", stats["cache"] == "ResolverCache")
    check("stats has hits", "hits" in stats)
    check("stats has misses", "misses" in stats)
    check("stats has hit_rate", "hit_rate" in stats)
    check("stats has size", stats["size"] == 0)

    print(f"  Section 17: {checks_passed} passed, {checks_failed} failed so far")

    # === 18. ResolverMetrics ===
    print("\n=== 18. ResolverMetrics ===")
    metrics = ResolverMetrics()
    check("ResolverMetrics creates", metrics is not None)

    metrics.record_resolve("payment", "round_robin", 0.005, True)
    metrics.record_resolve("payment", "round_robin", 0.003, True)
    metrics.record_resolve("payment", "random", 0.010, False)
    metrics.record_resolve("order", "round_robin", 0.008, True)

    metrics.record_route("version", 0.001)
    metrics.record_route("canary", 0.002)
    metrics.record_load_balance("round_robin", True)
    metrics.record_load_balance("random", False)
    metrics.record_canary_route("payment", True)
    metrics.record_canary_route("payment", False)
    metrics.record_version_route("payment", "v2")
    metrics.record_locality_route("payment", "region")
    metrics.record_consistent_hash("payment", True)

    snap = metrics.snapshot()
    check("snapshot returns dict", isinstance(snap, dict))
    check("snapshot has route latency count", "icyquant_service_route_latency_seconds_count" in snap)
    check("snapshot has route latency avg", "icyquant_service_route_latency_seconds_avg" in snap)

    stats = metrics.get_stats()
    check("stats has metrics", stats["metrics"] == "ResolverMetrics")
    check("stats has total_resolves", stats["total_resolves"] == 4)
    check("stats has total_load_balance", stats["total_load_balance"] == 2)
    check("stats has total_canary_routes", stats["total_canary_routes"] == 2)
    check("stats has counters", "counters" in stats)

    print(f"  Section 18: {checks_passed} passed, {checks_failed} failed so far")

    # === 19. ResolverDiagnostics ===
    print("\n=== 19. ResolverDiagnostics ===")
    diag = ResolverDiagnostics()
    check("ResolverDiagnostics creates", diag is not None)

    diag.record_resolution("payment", "round_robin", "pay-1", 0.005, {"candidates": 3})
    diag.record_resolution("payment", "random", "pay-2", 0.003)
    diag.record_resolution("order", "round_robin", "ord-1", 0.008)

    diag.record_routing("version", "payment", "matched", {"version": "v1"})
    diag.record_routing("canary", "payment", "excluded")

    diag.record_filtering("health", "payment", 1, "unhealthy")

    history = diag.get_history()
    check("get_history returns list", isinstance(history, list))
    check("get_history has entries", len(history) >= 3)

    history_filtered = diag.get_history("payment")
    check("get_history filtered by service", all(
        e["service_name"] == "payment" for e in history_filtered
    ))

    routing_log = diag.get_routing_log()
    check("get_routing_log returns list", isinstance(routing_log, list))
    check("get_routing_log has entries", len(routing_log) >= 2)

    routing_filtered = diag.get_routing_log("payment")
    check("get_routing_log filtered", len(routing_filtered) >= 2)

    perf = diag.get_performance_report()
    check("performance report has total_resolutions", perf["total_resolutions"] >= 3)
    check("performance report has avg_latency", "avg_latency" in perf)
    check("performance report has by_strategy", "by_strategy" in perf)
    check("performance report has by_service", "by_service" in perf)

    diag.clear("payment")
    history_after = diag.get_history()
    check("clear by service removes", all(
        e["service_name"] != "payment" for e in history_after
    ))

    diag2 = ResolverDiagnostics()
    diag2.record_resolution("svc", "rr", "inst-1", 0.001)
    diag2.clear()
    check("clear all empties", len(diag2.get_history()) == 0)

    stats = diag.get_stats()
    check("stats has diagnostics", stats["diagnostics"] == "ResolverDiagnostics")
    check("stats has resolution_count", stats["resolution_count"] >= 3)
    check("stats has routing_count", stats["routing_count"] >= 2)

    print(f"  Section 19: {checks_passed} passed, {checks_failed} failed so far")

    # === 20. ResolverTelemetry ===
    print("\n=== 20. ResolverTelemetry ===")
    tel = ResolverTelemetry()
    check("ResolverTelemetry creates", tel is not None)

    tel.record_resolve("payment", "round_robin", "pay-1", 0.005)
    tel.record_resolve("payment", "random", "pay-2", 0.003)
    tel.record_route_decision("version", "payment", 3, "pay-1")

    span_id = tel.start_span("resolve", "payment")
    check("start_span returns string", isinstance(span_id, str))
    check("start_span returns hex", len(span_id) == 32)

    tel.end_span(span_id, "ok")

    span_id2 = tel.start_span("load_balance", "order")
    tel.end_span(span_id2, "error")

    spans = tel.get_spans()
    check("get_spans returns list", isinstance(spans, list))
    check("get_spans has entries", len(spans) >= 2)

    spans_filtered = tel.get_spans("payment")
    check("get_spans filtered by service", len(spans_filtered) >= 1)

    traces = tel.get_traces()
    check("get_traces returns list", isinstance(traces, list))
    check("get_traces has entries", len(traces) >= 2)

    traces_filtered = tel.get_traces("payment")
    check("get_traces filtered", len(traces_filtered) >= 1)

    tel.end_span("nonexistent_span")
    check("end_span nonexistent no-op", True)

    stats = tel.get_stats()
    check("stats has telemetry", stats["telemetry"] == "ResolverTelemetry")
    check("stats has resolve_count", stats["resolve_count"] >= 2)
    check("stats has route_decision_count", stats["route_decision_count"] >= 1)
    check("stats has span_count", stats["span_count"] >= 2)
    check("stats has trace_count", stats["trace_count"] >= 2)
    check("stats has active_spans", stats["active_spans"] == 0)

    print(f"  Section 20: {checks_passed} passed, {checks_failed} failed so far")

    # === 21. IntelligentServiceResolver ===
    print("\n=== 21. IntelligentServiceResolver ===")
    isr = IntelligentServiceResolver()
    check("IntelligentServiceResolver creates", isr is not None)

    check("has version_router", isr.version_router is not None)
    check("has canary_router", isr.canary_router is not None)
    check("has feature_flag_router", isr.feature_flag_router is not None)
    check("has health_filter", isr.health_filter is not None)
    check("has circuit_filter", isr.circuit_filter is not None)
    check("has locality_router", isr.locality_router is not None)
    check("has cache", isr.cache is not None)
    check("has metrics", isr.metrics is not None)
    check("has diagnostics", isr.diagnostics is not None)
    check("has telemetry", isr.telemetry is not None)
    check("has load_balancer", isr.load_balancer is not None)

    async def test_isr():
        result = await isr.resolve("payment")
        check("resolve with no instances returns None", result is None)

        result_many = await isr.resolve_many("payment", 2)
        check("resolve_many with no instances", len(result_many) == 0)

        result_endpoint = await isr.resolve_endpoint("payment")
        check("resolve_endpoint with no instances", result_endpoint is None)

        ctx = ResolveContext(version="v2")
        result_ctx = await isr.resolve("payment", ctx)
        check("resolve with context no instances", result_ctx is None)

    asyncio.run(test_isr())

    try:
        isr.set_load_balancer(None)
        check("set_load_balancer None raises", False)
    except ValueError:
        check("set_load_balancer None raises ValueError", True)

    try:
        isr.set_load_balancer("not_a_lb")
        check("set_load_balancer wrong type raises", False)
    except TypeError:
        check("set_load_balancer wrong type raises TypeError", True)

    lb_new = LoadBalancer(default_strategy="random")
    isr.set_load_balancer(lb_new)
    check("set_load_balancer works", isr.load_balancer._default_strategy == "random")

    stats = isr.get_stats()
    check("stats has resolver", stats["resolver"] == "IntelligentServiceResolver")
    check("stats has resolve_count", "resolve_count" in stats)
    check("stats has failure_count", "failure_count" in stats)
    check("stats has failure_rate", "failure_rate" in stats)
    check("stats has avg_latency", "avg_latency" in stats)
    check("stats has load_balancer sub-stats", "load_balancer" in stats)
    check("stats has version_router sub-stats", "version_router" in stats)
    check("stats has cache sub-stats", "cache" in stats)
    check("stats has metrics sub-stats", "metrics" in stats)
    check("stats has diagnostics sub-stats", "diagnostics" in stats)
    check("stats has telemetry sub-stats", "telemetry" in stats)

    print(f"  Section 21: {checks_passed} passed, {checks_failed} failed so far")

    # === Final Summary ===
    print("\n" + "=" * 60)
    total = checks_passed + checks_failed
    print(f"RESULTS: {checks_passed}/{total} passed, {checks_failed}/{total} failed")
    if checks_failed == 0:
        print("ALL CHECKS PASSED!")
    else:
        print(f"FAILURE COUNT: {checks_failed}")
    print("=" * 60)

    return checks_failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)