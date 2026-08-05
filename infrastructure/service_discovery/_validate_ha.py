import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from infrastructure.service_discovery.ha import (
    FailoverManager,
    SelfHealingEngine,
    AdaptiveRetryEngine,
    RetryBudget,
    ReplicaManager,
    TrafficDrain,
    GracefulEviction,
    RegistryRecovery,
    RegistrySnapshot,
    ClusterRebalancer,
    SplitBrainDetector,
    MultiRegistryFailover,
    HAController,
    HAState,
    HAStateMachine,
    HAScheduler,
    HAPolicy,
    HAPolicyManager,
    HAMetrics,
    HATelemetry,
    HAAudit,
    HADiagnostics,
    HAHealth,
)
from infrastructure.service_discovery.instance import ServiceInstance
from infrastructure.service_discovery.models import ServiceStatus

checks_passed = 0
checks_failed = 0


def check(name, condition):
    global checks_passed, checks_failed
    if condition:
        checks_passed += 1
    else:
        checks_failed += 1
        print(f"  [FAIL] {name}")


def make_instance(svc, iid, host="127.0.0.1", port=8080, weight=1, healthy=True, metadata=None):
    return ServiceInstance(
        service_name=svc,
        instance_id=iid,
        host=host,
        port=port,
        weight=weight,
        healthy=healthy,
        metadata=metadata or {},
        status=ServiceStatus.HEALTHY if healthy else ServiceStatus.UNHEALTHY,
    )


print("=" * 60)
print("ICYQuant Service Discovery HA - Comprehensive Validation")
print("=" * 60)

# ──────────────────────────────────────────────
# 1. FailoverManager
# ──────────────────────────────────────────────
print("\n=== 1. FailoverManager ===")


def test_failover_manager():
    fm = FailoverManager()

    r = asyncio.run(fm.detect("order_service", "inst-001"))
    check("1.1 detect returns dict", isinstance(r, dict))
    check("1.2 detect has service_name", r.get("service_name") == "order_service")
    check("1.3 detect has instance_id", r.get("instance_id") == "inst-001")
    check("1.4 detect has failed bool", isinstance(r.get("failed"), bool))
    check("1.5 detect has phi (float)", isinstance(r.get("phi"), float))
    check("1.6 detect has reason", isinstance(r.get("reason"), str))
    check("1.7 detect has timestamp", "timestamp" in r)
    check("1.8 detect reason when no detector", r.get("reason") == "no_detector")

    r2 = asyncio.run(fm.detect("order_service", "inst-001"))
    check("1.9 detection_count incremented", fm.get_stats()["detection_count"] == 2)

    healthy = [
        make_instance("order_service", "inst-002", weight=5),
        make_instance("order_service", "inst-003", weight=10),
    ]
    p = asyncio.run(fm.promote("order_service", healthy))
    check("1.10 promote returns dict", isinstance(p, dict))
    check("1.11 promote promoted True", p.get("promoted") is True)
    check("1.12 promoted_instance_id is inst-003 (highest weight)", p.get("promoted_instance_id") == "inst-003")
    check("1.13 promoted_instance_host present", "promoted_instance_host" in p)
    check("1.14 promoted_instance_port present", "promoted_instance_port" in p)
    check("1.15 promote has timestamp", "timestamp" in p)

    empty_p = asyncio.run(fm.promote("order_service", []))
    check("1.16 promote with empty list returns promoted=False", empty_p.get("promoted") is False)
    check("1.17 promote empty reason", empty_p.get("reason") == "no_healthy_instances")

    rcv = asyncio.run(fm.recover("order_service", "inst-001"))
    check("1.18 recover returns dict", isinstance(rcv, dict))
    check("1.19 recover has recovered bool", isinstance(rcv.get("recovered"), bool))
    check("1.20 recover has stages dict", isinstance(rcv.get("stages"), dict))
    check("1.21 recover has drain stage", "drain" in rcv["stages"])
    check("1.22 recover has deregister stage", "deregister" in rcv["stages"])
    check("1.23 recover has restart stage", "restart" in rcv["stages"])
    check("1.24 recover has reregister stage", "reregister" in rcv["stages"])

    replicas = [
        make_instance("order_service", "inst-001", healthy=False),
        make_instance("order_service", "inst-002", weight=5),
        make_instance("order_service", "inst-003", weight=8),
    ]
    fo = asyncio.run(fm.execute_failover("order_service", "inst-001", replicas))
    check("1.25 execute_failover returns dict", isinstance(fo, dict))
    check("1.26 failover_executed is True", fo.get("failover_executed") is True)
    check("1.27 failover has detection", "detection" in fo)
    check("1.28 failover has promotion", "promotion" in fo)
    check("1.29 failover has traffic_switched", isinstance(fo.get("traffic_switched"), bool))
    check("1.30 failover has recovery", "recovery" in fo)

    fo_no_healthy = asyncio.run(fm.execute_failover(
        "order_service", "inst-001",
        [make_instance("order_service", "inst-002", healthy=False)]
    ))
    check("1.31 failover with no healthy replicas fails", fo_no_healthy.get("failover_executed") is False)
    check("1.32 failover no healthy reason", fo_no_healthy.get("reason") == "no_healthy_replicas")

    st = fm.get_stats()
    check("1.33 get_stats returns dict", isinstance(st, dict))
    check("1.34 stats has detection_count", "detection_count" in st)
    check("1.35 stats has promotion_count", "promotion_count" in st)
    check("1.36 stats has failover_count", "failover_count" in st)
    check("1.37 stats has recovery_count", "recovery_count" in st)
    check("1.38 stats has failures_detected", "failures_detected" in st)
    check("1.39 stats has history_size", "history_size" in st)
    check("1.40 stats has max_history", "max_history" in st)

    r = repr(fm)
    check("1.41 repr contains FailoverManager", "FailoverManager" in r)


test_failover_manager()

# ──────────────────────────────────────────────
# 2. SelfHealingEngine
# ──────────────────────────────────────────────
print("\n=== 2. SelfHealingEngine ===")


def test_self_healing_engine():
    she = SelfHealingEngine()

    d = asyncio.run(she.diagnose("node_failure", "order_service"))
    check("2.1 diagnose returns dict", isinstance(d, dict))
    check("2.2 diagnose diagnosed True", d.get("diagnosed") is True)
    check("2.3 diagnose has failure_type", d.get("failure_type") == "node_failure")
    check("2.4 diagnose has service_name", d.get("service_name") == "order_service")
    check("2.5 diagnose has recommended_action", isinstance(d.get("recommended_action"), str))
    check("2.6 diagnose has confidence (float)", isinstance(d.get("confidence"), float))
    check("2.7 diagnose has details", isinstance(d.get("details"), dict))
    check("2.8 diagnose has timestamp", "timestamp" in d)
    check("2.9 diagnose node_failure action", d.get("recommended_action") == "restart_node")

    d2 = asyncio.run(she.diagnose("unknown_type", "svc"))
    check("2.10 diagnose unknown type returns investigate", d2.get("recommended_action") == "investigate")

    h = asyncio.run(she.heal("node_failure", "order_service", "inst-001"))
    check("2.11 heal returns dict", isinstance(h, dict))
    check("2.12 heal has healed bool", isinstance(h.get("healed"), bool))
    check("2.13 heal has failure_type", h.get("failure_type") == "node_failure")
    check("2.14 heal has service_name", h.get("service_name") == "order_service")
    check("2.15 heal has outcome", isinstance(h.get("outcome"), dict))
    check("2.16 heal node_failure is healed", h.get("healed") is True)

    h_unk = asyncio.run(she.heal("nonexistent_type", "svc"))
    check("2.17 heal unknown type returns healed=False", h_unk.get("healed") is False)
    check("2.18 heal unknown reason is no_handler", h_unk.get("reason") == "no_handler")

    v = asyncio.run(she.verify("order_service"))
    check("2.19 verify returns bool", isinstance(v, bool))
    check("2.20 verify without registry returns True", v is True)

    def custom_handler(svc, iid):
        return {"healed": True, "action": "custom"}

    she.register_handler("custom_failure", custom_handler)
    hc = asyncio.run(she.heal("custom_failure", "svc"))
    check("2.21 register_handler works", hc.get("healed") is True)

    try:
        she.register_handler("", lambda s, i: {"healed": True})
        check("2.22 empty failure_type raises", False)
    except ValueError:
        check("2.22 empty failure_type raises ValueError", True)

    try:
        she.register_handler("test", "not_callable")
        check("2.23 non-callable handler raises", False)
    except TypeError:
        check("2.23 non-callable raises TypeError", True)

    st = she.get_stats()
    check("2.24 get_stats returns dict", isinstance(st, dict))
    check("2.25 stats has diagnose_count", "diagnose_count" in st)
    check("2.26 stats has heal_count", "heal_count" in st)
    check("2.27 stats has verify_count", "verify_count" in st)
    check("2.28 stats has healed_count", "healed_count" in st)
    check("2.29 stats has failed_count", "failed_count" in st)
    check("2.30 stats has registered_handlers", "registered_handlers" in st)
    check("2.31 builtin handlers registered", len(st["registered_handlers"]) >= 6)

    r = repr(she)
    check("2.32 repr contains SelfHealingEngine", "SelfHealingEngine" in r)


test_self_healing_engine()

# ──────────────────────────────────────────────
# 3. AdaptiveRetryEngine + RetryBudget
# ──────────────────────────────────────────────
print("\n=== 3. AdaptiveRetryEngine + RetryBudget ===")


def test_retry_engine():
    budget = RetryBudget(max_retries=3, window=60.0)
    check("3.1 RetryBudget instantiated", isinstance(budget, RetryBudget))

    c1 = budget.consume()
    check("3.2 first consume succeeds", c1 is True)
    c2 = budget.consume()
    check("3.3 second consume succeeds", c2 is True)
    c3 = budget.consume()
    check("3.4 third consume succeeds", c3 is True)
    c4 = budget.consume()
    check("3.4b budget exhausted after max_retries", c4 is False)

    rem = budget.remaining()
    check("3.5 remaining returns int", isinstance(rem, int))
    check("3.6 remaining is 0 after exhaustion", rem == 0)

    bs = budget.get_stats()
    check("3.7 budget get_stats returns dict", isinstance(bs, dict))
    check("3.8 budget stats has max_retries", "max_retries" in bs)
    check("3.9 budget stats has consumed", "consumed" in bs)
    check("3.10 budget stats has rejected", "rejected" in bs)

    r = repr(budget)
    check("3.11 budget repr contains RetryBudget", "RetryBudget" in r)

    engine = AdaptiveRetryEngine(max_retries=2, base_delay=0.01, max_delay=5.0, jitter=0.0)

    call_count = [0]

    def succeed():
        call_count[0] += 1
        return "success_value"

    result = asyncio.run(engine.execute(succeed))
    check("3.12 execute returns operation result", result == "success_value")
    check("3.13 execute called operation once (first try)", call_count[0] == 1)

    call_count2 = [0]

    def fail_then_succeed():
        call_count2[0] += 1
        if call_count2[0] < 2:
            raise ValueError("fail")
        return "recovered"

    result2 = asyncio.run(engine.execute(fail_then_succeed))
    check("3.14 execute retry succeeds", result2 == "recovered")
    check("3.15 execute retried once", call_count2[0] == 2)

    call_count3 = [0]

    def always_fail():
        call_count3[0] += 1
        raise RuntimeError("always fails")

    try:
        asyncio.run(engine.execute(always_fail))
        check("3.16 always_fail raises", False)
    except RuntimeError:
        check("3.16 always_fail raises last exception", True)
    check("3.17 always_fail called max_retries+1 times", call_count3[0] == 3)

    budget2 = RetryBudget(max_retries=2, window=60.0)
    call_count4 = [0]

    def fail_with_budget():
        call_count4[0] += 1
        raise ValueError("fail")

    try:
        asyncio.run(engine.execute_with_budget(fail_with_budget, budget2))
        check("3.18 execute_with_budget raises", False)
    except ValueError:
        check("3.18 execute_with_budget raises", True)

    eng_st = engine.get_stats()
    check("3.19 engine get_stats returns dict", isinstance(eng_st, dict))
    check("3.20 engine stats has retry_count", "retry_count" in eng_st)
    check("3.21 engine stats has success_count", "success_count" in eng_st)
    check("3.22 engine stats has failure_count", "failure_count" in eng_st)

    engine.reset()
    check("3.23 reset sets retry_count to 0", engine.get_stats()["retry_count"] == 0)

    r = repr(engine)
    check("3.24 engine repr contains AdaptiveRetryEngine", "AdaptiveRetryEngine" in r)


test_retry_engine()

# ──────────────────────────────────────────────
# 4. ReplicaManager
# ──────────────────────────────────────────────
print("\n=== 4. ReplicaManager ===")


def test_replica_manager():
    rm = ReplicaManager()

    inst_a = make_instance("order", "inst-a", weight=10)
    inst_b = make_instance("order", "inst-b", weight=5)
    inst_c = make_instance("order", "inst-c", weight=3)

    rm.add_replica("order", inst_a, priority=0)
    rm.add_replica("order", inst_b, priority=1)
    rm.add_replica("order", inst_c, priority=2)

    reps = rm.get_replicas("order")
    check("4.1 get_replicas returns list", isinstance(reps, list))
    check("4.2 get_replicas has 3 entries", len(reps) == 3)

    sel = rm.select_replica("order", strategy="priority")
    check("4.3 select priority returns ServiceInstance", isinstance(sel, ServiceInstance))
    check("4.4 select priority returns highest priority (inst-a)", sel.instance_id == "inst-a")

    sel_health = rm.select_replica("order", strategy="health-based")
    check("4.5 select health-based returns instance", isinstance(sel_health, ServiceInstance))
    check("4.6 select health-based weight check", sel_health.weight >= 3)

    sel_zone = rm.select_replica("order", strategy="zone-aware")
    check("4.7 select zone-aware returns instance", isinstance(sel_zone, ServiceInstance))

    prom = rm.promote("order", "inst-c")
    check("4.8 promote returns dict", isinstance(prom, dict))
    check("4.9 promote promoted True", prom.get("promoted") is True)
    check("4.10 promote new_priority 0", prom.get("new_priority") == 0)

    sel_after = rm.select_replica("order", strategy="priority")
    check("4.11 after promote, inst-c is selected", sel_after.instance_id == "inst-c")

    rm.remove_replica("order", "inst-b")
    reps2 = rm.get_replicas("order")
    check("4.12 remove_replica removes instance", len(reps2) == 2)

    prom_unk = rm.promote("order", "unknown")
    check("4.13 promote unknown returns False", prom_unk.get("promoted") is False)
    check("4.14 promote unknown reason", prom_unk.get("reason") == "not_found")

    sel_empty = rm.select_replica("nonexistent", strategy="priority")
    check("4.15 select from empty returns None", sel_empty is None)

    rm.add_replica("svc_new", make_instance("svc_new", "x1"))
    reps_new = rm.get_replicas("svc_new")
    check("4.16 add replica to new service works", len(reps_new) == 1)

    st = rm.get_stats()
    check("4.17 get_stats returns dict", isinstance(st, dict))
    check("4.18 stats has services_with_replicas", "services_with_replicas" in st)
    check("4.19 stats has total_replicas", "total_replicas" in st)
    check("4.20 stats has add_count", "add_count" in st)
    check("4.21 stats has remove_count", "remove_count" in st)
    check("4.22 stats has promote_count", "promote_count" in st)
    check("4.23 stats has select_count", "select_count" in st)

    r = repr(rm)
    check("4.24 repr contains ReplicaManager", "ReplicaManager" in r)


test_replica_manager()

# ──────────────────────────────────────────────
# 5. TrafficDrain
# ──────────────────────────────────────────────
print("\n=== 5. TrafficDrain ===")


def test_traffic_drain():
    td = TrafficDrain(timeout=5.0)

    check("5.1 is_draining returns False initially", td.is_draining("svc", "inst-1") is False)

    asyncio.run(td.begin_drain("svc", "inst-1"))
    check("5.2 is_draining True after begin_drain", td.is_draining("svc", "inst-1") is True)

    status = td.get_drain_status("svc", "inst-1")
    check("5.3 get_drain_status returns dict", isinstance(status, dict))
    check("5.4 status has service_name", status.get("service_name") == "svc")
    check("5.5 status has instance_id", status.get("instance_id") == "inst-1")
    check("5.6 status has status field", "status" in status)

    result = asyncio.run(td.finish_drain("svc", "inst-1"))
    check("5.7 finish_drain returns dict", isinstance(result, dict))
    check("5.8 finish_drain completed True", result.get("completed") is True)
    check("5.9 finish_drain active_requests 0", result.get("active_requests") == 0)

    check("5.10 is_draining False after finish", td.is_draining("svc", "inst-1") is False)

    full = asyncio.run(td.drain("svc2", "inst-2", current_requests=0))
    check("5.11 drain returns dict", isinstance(full, dict))
    check("5.12 drain has drained bool", isinstance(full.get("drained"), bool))
    check("5.13 drain has stages dict", isinstance(full.get("stages"), dict))
    check("5.14 drain has duration_s", "duration_s" in full)

    status2 = td.get_drain_status("nonexistent", "x")
    check("5.15 get_drain_status for unknown returns None", status2 is None)

    st = td.get_stats()
    check("5.16 get_stats returns dict", isinstance(st, dict))
    check("5.17 stats has timeout", "timeout" in st)
    check("5.18 stats has total_drains", "total_drains" in st)
    check("5.19 stats has completed_drains", "completed_drains" in st)

    r = repr(td)
    check("5.20 repr contains TrafficDrain", "TrafficDrain" in r)


test_traffic_drain()

# ──────────────────────────────────────────────
# 6. GracefulEviction
# ──────────────────────────────────────────────
print("\n=== 6. GracefulEviction ===")


def test_graceful_eviction():
    ge = GracefulEviction()

    check("6.1 is_evicting False initially", ge.is_evicting("svc", "inst-1") is False)

    ev = asyncio.run(ge.evict("svc", "inst-1", mode="manual"))
    check("6.2 evict returns dict", isinstance(ev, dict))
    check("6.3 evict has evicted bool", isinstance(ev.get("evicted"), bool))
    check("6.4 evict has stages dict", isinstance(ev.get("stages"), dict))
    check("6.5 evict has drain stage", "drain" in ev["stages"])
    check("6.6 evict has deregister stage", "deregister" in ev["stages"])
    check("6.7 evict has shutdown stage", "shutdown" in ev["stages"])
    check("6.8 evict has mode", ev.get("mode") == "manual")
    check("6.9 evict has timestamp", "timestamp" in ev)

    ev2 = asyncio.run(ge.evict("svc", "inst-2", mode="upgrade"))
    check("6.10 evict with upgrade mode works", ev2.get("mode") == "upgrade")

    ev3 = asyncio.run(ge.evict("svc", "inst-3", mode="invalid_mode"))
    check("6.11 invalid mode falls back to manual", ev3.get("mode") == "manual")

    ge.cancel_eviction("svc", "inst-99")
    check("6.12 cancel_eviction for unknown does not raise", True)

    st = ge.get_stats()
    check("6.13 get_stats returns dict", isinstance(st, dict))
    check("6.14 stats has active_evictions", "active_evictions" in st)
    check("6.15 stats has total_evictions", "total_evictions" in st)
    check("6.16 stats has batch_count", "batch_count" in st)
    check("6.17 stats has cancel_count", "cancel_count" in st)
    check("6.18 stats has completed_count", "completed_count" in st)

    evict_batch = asyncio.run(ge.evict_batch([
        ("svc", "inst-10"),
        ("svc", "inst-11"),
    ]))
    check("6.19 evict_batch returns list", isinstance(evict_batch, list))
    check("6.20 evict_batch has 2 results", len(evict_batch) == 2)

    r = repr(ge)
    check("6.21 repr contains GracefulEviction", "GracefulEviction" in r)


test_graceful_eviction()

# ──────────────────────────────────────────────
# 7. RegistryRecovery
# ──────────────────────────────────────────────
print("\n=== 7. RegistryRecovery ===")


def test_registry_recovery():
    rr = RegistryRecovery()

    snap = {
        "version": 1,
        "services": {
            "order": [
                {"service_name": "order", "instance_id": "i1", "host": "h1", "port": 8080, "weight": 1, "healthy": True},
            ],
        },
    }
    ls = asyncio.run(rr.load_snapshot(snap))
    check("7.1 load_snapshot returns dict", isinstance(ls, dict))
    check("7.2 load_snapshot loaded True", ls.get("loaded") is True)
    check("7.3 load_snapshot has services_restored", "services_restored" in ls)
    check("7.4 load_snapshot has snapshot_version", ls.get("snapshot_version") == 1)
    check("7.5 load_snapshot has timestamp", "timestamp" in ls)

    events = [
        {"event_type": "service.registered", "service_name": "order", "instance_id": "i1", "data": {"weight": 5}},
        {"event_type": "service.deregistered", "service_name": "order", "instance_id": "i1"},
    ]
    re = asyncio.run(rr.replay_events(events))
    check("7.6 replay_events returns dict", isinstance(re, dict))
    check("7.7 replay_events replayed True", re.get("replayed") is True)
    check("7.8 replay_events has events_total", re.get("events_total") == 2)
    check("7.9 replay_events has events_replayed", re.get("events_replayed") == 2)
    check("7.10 replay_events has events_failed", re.get("events_failed") == 0)

    vc = asyncio.run(rr.verify_consistency())
    check("7.11 verify_consistency returns dict", isinstance(vc, dict))
    check("7.12 verify_consistency consistent bool", isinstance(vc.get("consistent"), bool))
    check("7.13 verify_consistency has checks_performed", isinstance(vc.get("checks_performed"), list))
    check("7.14 verify_consistency has timestamp", "timestamp" in vc)

    resume = asyncio.run(rr.resume())
    check("7.15 resume returns dict", isinstance(resume, dict))
    check("7.16 resume resumed True", resume.get("resumed") is True)
    check("7.17 resume has state", isinstance(resume.get("state"), dict))

    st = rr.get_stats()
    check("7.18 get_stats returns dict", isinstance(st, dict))
    check("7.19 stats has phase", "phase" in st)
    check("7.20 stats has snapshot_loaded", "snapshot_loaded" in st)
    check("7.21 stats has events_replayed", "events_replayed" in st)
    check("7.22 stats has consistency_verified", "consistency_verified" in st)
    check("7.23 stats has resumed", "resumed" in st)
    check("7.24 stats has recovery_count", "recovery_count" in st)

    r = repr(rr)
    check("7.25 repr contains RegistryRecovery", "RegistryRecovery" in r)


test_registry_recovery()

# ──────────────────────────────────────────────
# 8. RegistrySnapshot
# ──────────────────────────────────────────────
print("\n=== 8. RegistrySnapshot ===")


def test_registry_snapshot():
    rs = RegistrySnapshot(version=0)

    svc_data = {
        "order": [{"instance_id": "o1", "host": "h1", "port": 8080}],
        "payment": [{"instance_id": "p1", "host": "h2", "port": 8081}],
    }
    snap1 = rs.create(svc_data)
    check("8.1 create returns dict", isinstance(snap1, dict))
    check("8.2 create has version", snap1.get("version") == 1)
    check("8.3 create has created_at", "created_at" in snap1)
    check("8.4 create has services", isinstance(snap1.get("services"), dict))
    check("8.5 create has checksum", isinstance(snap1.get("checksum"), str))
    check("8.6 services count is 2", len(snap1["services"]) == 2)

    snap2 = rs.create({"order": []})
    check("8.7 second create increments version", snap2.get("version") == 2)

    restored = rs.restore(snap1)
    check("8.8 restore returns dict", isinstance(restored, dict))
    check("8.9 restore restored True", restored.get("restored") is True)
    check("8.10 restore has snapshot_version", restored.get("snapshot_version") == 1)
    check("8.11 restore has checksum_valid", restored.get("checksum_valid") is True)

    latest = rs.get_latest()
    check("8.12 get_latest returns dict", isinstance(latest, dict))
    check("8.13 get_latest is version 2", latest.get("version") == 2)

    hist = rs.get_history(limit=5)
    check("8.14 get_history returns list", isinstance(hist, list))
    check("8.15 get_history has entries", len(hist) >= 2)
    check("8.16 history entries have version", "version" in hist[0])

    cmp = rs.compare(snap1, snap2)
    check("8.17 compare returns dict", isinstance(cmp, dict))
    check("8.18 compare has added", isinstance(cmp.get("added"), list))
    check("8.19 compare has removed", isinstance(cmp.get("removed"), list))
    check("8.20 compare has modified", isinstance(cmp.get("modified"), list))
    check("8.21 compare has equal bool", isinstance(cmp.get("equal"), bool))

    st = rs.get_stats()
    check("8.22 get_stats returns dict", isinstance(st, dict))
    check("8.23 stats has current_version", "current_version" in st)
    check("8.24 stats has total_snapshots", "total_snapshots" in st)
    check("8.25 stats has create_count", "create_count" in st)
    check("8.26 stats has restore_count", "restore_count" in st)
    check("8.27 stats has compare_count", "compare_count" in st)

    r = repr(rs)
    check("8.28 repr contains RegistrySnapshot", "RegistrySnapshot" in r)


test_registry_snapshot()

# ──────────────────────────────────────────────
# 9. ClusterRebalancer
# ──────────────────────────────────────────────
print("\n=== 9. ClusterRebalancer ===")


def test_cluster_rebalancer():
    cr = ClusterRebalancer()

    insts = [
        make_instance("svc", "i1", weight=10, metadata={"cpu_usage": 0.8, "memory_usage": 0.6, "connections": 100, "latency_ms": 50}),
        make_instance("svc", "i2", weight=5, metadata={"cpu_usage": 0.2, "memory_usage": 0.3, "connections": 50, "latency_ms": 10}),
        make_instance("svc", "i3", weight=3, metadata={"cpu_usage": 0.5, "memory_usage": 0.4, "connections": 75, "latency_ms": 30}),
    ]

    ana = asyncio.run(cr.analyze(insts))
    check("9.1 analyze returns dict", isinstance(ana, dict))
    check("9.2 analyze has analyzed True", ana.get("analyzed") is True)
    check("9.3 analyze has instance_count", ana.get("instance_count") == 3)
    check("9.4 analyze has balance_score", isinstance(ana.get("balance_score"), float))
    check("9.5 analyze has instances list", isinstance(ana.get("instances"), list))
    check("9.6 analyze instance metrics has cpu_usage", "cpu_usage" in ana["instances"][0])
    check("9.7 analyze has total_weight", isinstance(ana.get("total_weight"), int))

    weights = cr.compute_weights(insts)
    check("9.8 compute_weights returns dict", isinstance(weights, dict))
    check("9.9 compute_weights has all instances", len(weights) == 3)
    check("9.10 compute_weights values are ints", all(isinstance(v, int) for v in weights.values()))
    check("9.11 compute_weights keys match instance_ids", set(weights.keys()) == {"i1", "i2", "i3"})

    reb = asyncio.run(cr.rebalance(insts))
    check("9.12 rebalance returns dict", isinstance(reb, dict))
    check("9.13 rebalance rebalanced True", reb.get("rebalanced") is True)
    check("9.14 rebalance has adjustments list", isinstance(reb.get("adjustments"), list))
    check("9.15 rebalance has adjustments_count", isinstance(reb.get("adjustments_count"), int))

    empty_ana = asyncio.run(cr.analyze([]))
    check("9.16 analyze empty returns instance_count 0", empty_ana.get("instance_count") == 0)
    check("9.17 analyze empty balance_score 1.0", empty_ana.get("balance_score") == 1.0)

    empty_weights = cr.compute_weights([])
    check("9.18 compute_weights empty returns dict", empty_weights == {})

    st = cr.get_stats()
    check("9.19 get_stats returns dict", isinstance(st, dict))
    check("9.20 stats has analysis_count", "analysis_count" in st)
    check("9.21 stats has rebalance_count", "rebalance_count" in st)

    r = repr(cr)
    check("9.22 repr contains ClusterRebalancer", "ClusterRebalancer" in r)


test_cluster_rebalancer()

# ──────────────────────────────────────────────
# 10. SplitBrainDetector
# ──────────────────────────────────────────────
print("\n=== 10. SplitBrainDetector ===")


def test_split_brain_detector():
    sbd = SplitBrainDetector()

    nodes_no_pb = [
        {"node_id": "n1", "role": "follower", "epoch": 1, "registry_version": 1},
        {"node_id": "n2", "role": "follower", "epoch": 1, "registry_version": 1},
    ]
    r = sbd.detect(nodes_no_pb)
    check("10.1 detect no split-brain returns None", r is None)

    nodes_leader_conflict = [
        {"node_id": "n1", "role": "leader", "epoch": 1},
        {"node_id": "n2", "role": "leader", "epoch": 2},
    ]
    r2 = sbd.detect(nodes_leader_conflict)
    check("10.2 detect leader conflict returns dict", isinstance(r2, dict))
    check("10.3 detect leader conflict detected True", r2.get("detected") is True)
    check("10.4 detect leader conflict type", r2.get("type") == "leader_conflict")

    nodes_registry_conflict = [
        {"node_id": "n1", "role": "follower", "epoch": 1, "registry_version": 1},
        {"node_id": "n2", "role": "follower", "epoch": 1, "registry_version": 2},
        {"node_id": "n3", "role": "follower", "epoch": 1, "registry_version": 1},
    ]
    r3 = sbd.detect(nodes_registry_conflict)
    check("10.5 detect registry conflict returns dict", isinstance(r3, dict))
    check("10.6 detect registry conflict type", r3.get("type") == "registry_conflict")

    check("10.7 check_quorum(3,2) is True", sbd.check_quorum(3, 2) is True)
    check("10.8 check_quorum(1,2) is False", sbd.check_quorum(1, 2) is False)
    check("10.9 check_quorum(4) default quorum", sbd.check_quorum(4) is True)
    check("10.10 check_quorum(0) is False", sbd.check_quorum(0) is False)

    node_a = {"node_id": "n1", "votes": 10, "epoch": 5}
    node_b = {"node_id": "n2", "votes": 5, "epoch": 3}
    res = asyncio.run(sbd.resolve(node_a, node_b, strategy="majority"))
    check("10.11 resolve majority returns dict", isinstance(res, dict))
    check("10.12 resolve majority resolved True", res.get("resolved") is True)
    check("10.13 resolve majority winner is n1", res.get("winner") == "n1")

    res2 = asyncio.run(sbd.resolve(node_a, node_b, strategy="epoch"))
    check("10.14 resolve epoch strategy works", res2.get("strategy") == "epoch_version")
    check("10.15 resolve epoch winner is n1 (higher epoch)", res2.get("winner") == "n1")

    res3 = asyncio.run(sbd.resolve(node_a, node_b, strategy="force"))
    check("10.16 resolve force strategy works", res3.get("strategy") == "force")

    ep = sbd.get_epoch()
    check("10.17 get_epoch returns int", isinstance(ep, int))
    new_ep = sbd.increment_epoch()
    check("10.18 increment_epoch increments", new_ep == ep + 1)

    st = sbd.get_stats()
    check("10.19 get_stats returns dict", isinstance(st, dict))
    check("10.20 stats has epoch", "epoch" in st)
    check("10.21 stats has detection_count", "detection_count" in st)
    check("10.22 stats has resolution_count", "resolution_count" in st)

    r = repr(sbd)
    check("10.23 repr contains SplitBrainDetector", "SplitBrainDetector" in r)


test_split_brain_detector()

# ──────────────────────────────────────────────
# 11. MultiRegistryFailover
# ──────────────────────────────────────────────
print("\n=== 11. MultiRegistryFailover ===")


def test_multi_registry_failover():
    mrf = MultiRegistryFailover()

    check("11.1 get_active_registry empty initially", mrf.get_active_registry() == "")

    mrf.add_registry("primary", object(), priority=0)
    check("11.2 get_active_registry is primary", mrf.get_active_registry() == "primary")

    mrf.add_registry("secondary", object(), priority=1)
    check("11.3 get_active_registry still primary", mrf.get_active_registry() == "primary")

    ar = mrf.get_active_registry()
    check("11.4 active_registry returns string", isinstance(ar, str))

    sw = asyncio.run(mrf.switch_to("secondary"))
    check("11.5 switch_to returns dict", isinstance(sw, dict))
    check("11.6 switch_to switched bool", isinstance(sw.get("switched"), bool))
    check("11.7 switch_to has target", sw.get("target") == "secondary")

    sw_unk = asyncio.run(mrf.switch_to("nonexistent"))
    check("11.8 switch_to unknown fails", sw_unk.get("switched") is False)
    check("11.9 switch_to unknown reason", sw_unk.get("reason") == "registry_not_found")

    fo = asyncio.run(mrf.failover())
    check("11.10 failover returns dict", isinstance(fo, dict))
    check("11.11 failover has failover bool", isinstance(fo.get("failover"), bool))

    mrf.remove_registry("secondary")
    check("11.12 remove_registry works", mrf.get_active_registry() == "primary")

    try:
        mrf.add_registry("", object())
        check("11.13 empty name raises", False)
    except ValueError:
        check("11.13 empty name raises ValueError", True)

    st = mrf.get_stats()
    check("11.14 get_stats returns dict", isinstance(st, dict))
    check("11.15 stats has active_registry", "active_registry" in st)
    check("11.16 stats has registry_count", "registry_count" in st)
    check("11.17 stats has switch_count", "switch_count" in st)
    check("11.18 stats has failover_count", "failover_count" in st)

    r = repr(mrf)
    check("11.19 repr contains MultiRegistryFailover", "MultiRegistryFailover" in r)


test_multi_registry_failover()

# ──────────────────────────────────────────────
# 12. HAController
# ──────────────────────────────────────────────
print("\n=== 12. HAController ===")


def test_ha_controller():
    hc = HAController()

    hc.register_component("failover", FailoverManager())
    hc.register_component("rebalancer", ClusterRebalancer())

    comp = hc.get_component("failover")
    check("12.1 get_component returns component", comp is not None)
    check("12.2 get_component returns FailoverManager", isinstance(comp, FailoverManager))

    comp_unk = hc.get_component("nonexistent")
    check("12.3 get_component unknown returns None", comp_unk is None)

    try:
        hc.register_component("", object())
        check("12.4 empty name raises", False)
    except ValueError:
        check("12.4 empty name raises ValueError", True)

    coord = asyncio.run(hc.coordinate())
    check("12.5 coordinate returns dict", isinstance(coord, dict))
    check("12.6 coordinate coordinated True", coord.get("coordinated") is True)
    check("12.7 coordinate has stages dict", isinstance(coord.get("stages"), dict))
    check("12.8 coordinate has heartbeat stage", "heartbeat" in coord["stages"])
    check("12.9 coordinate has failure_detection stage", "failure_detection" in coord["stages"])
    check("12.10 coordinate has failover stage", "failover" in coord["stages"])
    check("12.11 coordinate has recovery stage", "recovery" in coord["stages"])
    check("12.12 coordinate has rebalance stage", "rebalance" in coord["stages"])

    reb = asyncio.run(hc.rebalance())
    check("12.13 rebalance returns dict", isinstance(reb, dict))
    check("12.14 rebalance may be False due to missing instances", isinstance(reb.get("rebalanced"), bool))

    rec = asyncio.run(hc.recover())
    check("12.15 recover returns dict", isinstance(rec, dict))
    check("12.16 recover recovered True", rec.get("recovered") is True)

    st = hc.get_stats()
    check("12.17 get_stats returns dict", isinstance(st, dict))
    check("12.18 stats has coordinate_count", "coordinate_count" in st)
    check("12.19 stats has rebalance_count", "rebalance_count" in st)
    check("12.20 stats has recover_count", "recover_count" in st)
    check("12.21 stats has components", "components" in st)

    r = repr(hc)
    check("12.22 repr contains HAController", "HAController" in r)


test_ha_controller()

# ──────────────────────────────────────────────
# 13. HAStateMachine
# ──────────────────────────────────────────────
print("\n=== 13. HAStateMachine ===")


def test_ha_state_machine():
    sm = HAStateMachine(initial_state=HAState.HEALTHY)

    check("13.1 current_state is HEALTHY", sm.current_state() == HAState.HEALTHY)

    t1 = sm.transition(HAState.DEGRADED, "degraded detected")
    check("13.2 transition HEALTHY->DEGRADED works", t1.get("transitioned") is True)
    check("13.3 transition has from", t1.get("from") == "healthy")
    check("13.4 transition has to", t1.get("to") == "degraded")
    check("13.5 transition has reason", t1.get("reason") == "degraded detected")
    check("13.6 current_state is DEGRADED", sm.current_state() == HAState.DEGRADED)

    check("13.7 can_transition to FAILING from DEGRADED", sm.can_transition(HAState.FAILING) is True)
    check("13.8 can_transition to HEALTHY from DEGRADED", sm.can_transition(HAState.HEALTHY) is True)
    check("13.9 cannot transition to ISOLATED from DEGRADED", sm.can_transition(HAState.ISOLATED) is False)

    t2 = sm.transition(HAState.FAILING, "critical failure")
    check("13.10 transition DEGRADED->FAILING works", t2.get("transitioned") is True)

    t3 = sm.transition(HAState.HEALTHY, "invalid jump")
    check("13.11 invalid transition denied", t3.get("transitioned") is False)
    check("13.12 invalid transition has error", t3.get("error") == "invalid_transition")

    t4 = sm.transition(HAState.RECOVERING, "starting recovery")
    check("13.13 transition FAILING->RECOVERING works", t4.get("transitioned") is True)

    t5 = sm.transition(HAState.HEALTHY, "fully recovered")
    check("13.14 transition RECOVERING->HEALTHY works", t5.get("transitioned") is True)

    hist = sm.get_history(limit=10)
    check("13.15 get_history returns list", isinstance(hist, list))
    check("13.16 history has entries", len(hist) >= 4)
    check("13.17 history entries have from/to", ("from" in hist[0] or "from" in hist[0].get("data", {})))

    st = sm.get_stats()
    check("13.18 get_stats returns dict", isinstance(st, dict))
    check("13.19 stats has current_state", "current_state" in st)
    check("13.20 stats has transition_count", "transition_count" in st)
    check("13.21 stats has denied_count", "denied_count" in st)

    r = repr(sm)
    check("13.22 repr contains HAStateMachine", "HAStateMachine" in r)


test_ha_state_machine()

# ──────────────────────────────────────────────
# 14. HAScheduler
# ──────────────────────────────────────────────
print("\n=== 14. HAScheduler ===")


def test_ha_scheduler():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        hs = HAScheduler()

        check("14.1 is_running False initially", hs.is_running() is False)

        stats_before = hs.get_stats()
        check("14.2 default tasks registered", stats_before["task_count"] >= 6)

        hs.add_task("custom_task", lambda: {"done": True}, 30.0)
        stats_after = hs.get_stats()
        check("14.3 add_task increases task_count", stats_after["task_count"] >= 7)

        hs.remove_task("custom_task")
        stats_after2 = hs.get_stats()
        check("14.4 remove_task decreases task_count", stats_after2["task_count"] >= 6)

        try:
            hs.add_task("", lambda: None, 10.0)
            check("14.5 empty task name raises", False)
        except ValueError:
            check("14.5 empty task name raises ValueError", True)

        try:
            hs.add_task("bad", "not_callable", 10.0)
            check("14.6 non-callable fn raises", False)
        except TypeError:
            check("14.6 non-callable raises TypeError", True)

        try:
            hs.add_task("bad2", lambda: None, -1.0)
            check("14.7 negative interval raises", False)
        except ValueError:
            check("14.7 negative interval raises ValueError", True)

        loop.run_until_complete(hs.start())
        check("14.8 is_running True after start", hs.is_running() is True)

        loop.run_until_complete(hs.stop())
        check("14.9 is_running False after stop", hs.is_running() is False)

        st = hs.get_stats()
        check("14.10 get_stats returns dict", isinstance(st, dict))
        check("14.11 stats has running", "running" in st)
        check("14.12 stats has task_count", "task_count" in st)
        check("14.13 stats has start_count", "start_count" in st)
        check("14.14 stats has stop_count", "stop_count" in st)

        r = repr(hs)
        check("14.15 repr contains HAScheduler", "HAScheduler" in r)
    finally:
        loop.close()


test_ha_scheduler()

# ──────────────────────────────────────────────
# 15. HAPolicyManager
# ──────────────────────────────────────────────
print("\n=== 15. HAPolicyManager ===")


def test_ha_policy_manager():
    hpm = HAPolicyManager()

    pol = hpm.get_policy("order")
    check("15.1 get_policy default is AUTO_RECOVERY", pol == HAPolicy.AUTO_RECOVERY)

    hpm.set_policy("order", HAPolicy.MANUAL_RECOVERY)
    pol2 = hpm.get_policy("order")
    check("15.2 set_policy changes policy", pol2 == HAPolicy.MANUAL_RECOVERY)

    hpm.set_policy("payment", HAPolicy.PRIORITY_FAILOVER)
    pol3 = hpm.get_policy("payment")
    check("15.3 set_policy for different service", pol3 == HAPolicy.PRIORITY_FAILOVER)

    check("15.4 is_auto_recovery_enabled for order False", hpm.is_auto_recovery_enabled("order") is False)
    check("15.5 is_auto_recovery_enabled for unknown True", hpm.is_auto_recovery_enabled("unknown_svc") is True)

    check("15.6 is_maintenance_mode False initially", hpm.is_maintenance_mode() is False)
    hpm.set_maintenance_mode(True)
    check("15.7 is_maintenance_mode True after enable", hpm.is_maintenance_mode() is True)
    hpm.set_maintenance_mode(False)
    check("15.8 is_maintenance_mode False after disable", hpm.is_maintenance_mode() is False)

    try:
        hpm.set_policy("", HAPolicy.AUTO_RECOVERY)
        check("15.9 empty service_name raises", False)
    except ValueError:
        check("15.9 empty service_name raises ValueError", True)

    try:
        hpm.set_policy("svc", "not_a_policy")
        check("15.10 invalid policy raises", False)
    except TypeError:
        check("15.10 invalid policy raises TypeError", True)

    st = hpm.get_stats()
    check("15.11 get_stats returns dict", isinstance(st, dict))
    check("15.12 stats has service_count", "service_count" in st)
    check("15.13 stats has policy_distribution", "policy_distribution" in st)
    check("15.14 stats has maintenance_mode", "maintenance_mode" in st)
    check("15.15 stats has policy_change_count", "policy_change_count" in st)

    r = repr(hpm)
    check("15.16 repr contains HAPolicyManager", "HAPolicyManager" in r)


test_ha_policy_manager()

# ──────────────────────────────────────────────
# 16. HAMetrics
# ──────────────────────────────────────────────
print("\n=== 16. HAMetrics ===")


def test_ha_metrics():
    hm = HAMetrics()

    hm.record_failover("order", success=True, duration=0.5)
    hm.record_failover("order", success=False, duration=1.2)
    hm.record_self_healing("node_failure", "order", success=True)
    hm.record_registry_recovery(success=True, duration=3.0)
    hm.record_replica_promotion("order", success=True)
    hm.record_traffic_drain("order", duration=2.5)
    hm.record_cluster_rebalance(success=True, instance_count=3)
    hm.record_split_brain_detected(node_count=5)

    snap = hm.snapshot()
    check("16.1 snapshot returns dict", isinstance(snap, dict))
    check("16.2 snapshot has counters", isinstance(snap.get("counters"), dict))
    check("16.3 snapshot has labels", isinstance(snap.get("labels"), dict))
    check("16.4 snapshot has timers", isinstance(snap.get("timers"), dict))
    check("16.5 snapshot has recent_events", isinstance(snap.get("recent_events"), list))
    check("16.6 snapshot has timestamp", "timestamp" in snap)

    counters = snap["counters"]
    check("16.7 failover counter incremented", counters.get("icyquant_failover_total", 0) == 2)
    check("16.8 self_healing counter incremented", counters.get("icyquant_self_healing_total", 0) == 1)
    check("16.9 registry_recovery counter incremented", counters.get("icyquant_registry_recovery_total", 0) == 1)
    check("16.10 replica_promotion counter incremented", counters.get("icyquant_replica_promotion_total", 0) == 1)
    check("16.11 traffic_drain counter is float", isinstance(counters.get("icyquant_traffic_drain_seconds"), float))
    check("16.12 cluster_rebalance counter incremented", counters.get("icyquant_cluster_rebalance_total", 0) == 1)
    check("16.13 split_brain counter incremented", counters.get("icyquant_split_brain_detected_total", 0) == 1)

    events = snap["recent_events"]
    check("16.14 events list populated", len(events) >= 7)

    hm.reset()
    snap2 = hm.snapshot()
    check("16.15 reset zeros counters", snap2["counters"].get("icyquant_failover_total", -1) == 0)

    st = hm.get_stats()
    check("16.16 get_stats returns dict", isinstance(st, dict))
    check("16.17 stats has record_count", "record_count" in st)
    check("16.18 stats has counters", "counters" in st)

    r = repr(hm)
    check("16.19 repr contains HAMetrics", "HAMetrics" in r)


test_ha_metrics()

# ──────────────────────────────────────────────
# 17. HATelemetry
# ──────────────────────────────────────────────
print("\n=== 17. HATelemetry ===")


def test_ha_telemetry():
    ht = HATelemetry()

    sid = ht.start_span("failover", "order")
    check("17.1 start_span returns string", isinstance(sid, str))
    check("17.2 start_span returns non-empty", len(sid) > 0)

    spans = ht.get_spans()
    check("17.3 get_spans returns list", isinstance(spans, list))
    check("17.4 spans has at least 1 entry", len(spans) >= 1)
    check("17.5 span has operation", spans[0].get("operation") == "failover")
    check("17.6 span has service_name", spans[0].get("service_name") == "order")
    check("17.7 span has status started", spans[0].get("status") == "started")

    ht.end_span(sid, status="ok")
    spans2 = ht.get_spans()
    ended = spans2[0]
    check("17.8 end_span changes status", ended.get("status") == "ok")
    check("17.9 end_span sets duration", isinstance(ended.get("duration"), float))
    check("17.10 end_span sets ended_at", "ended_at" in ended)

    sid2 = ht.start_span("recovery", "order")
    ht.end_span(sid2, status="error")
    spans3 = ht.get_spans(service_name="order")
    check("17.11 filter by service_name works", len(spans3) >= 2)

    ht.record_failover("order", "i1", "i2", 0.5)
    ht.record_recovery("order", ["drain", "restart", "register"], success=True)
    ht.record_traffic_migration("order", "us-east", "us-west")

    st = ht.get_stats()
    check("17.12 get_stats returns dict", isinstance(st, dict))
    check("17.13 stats has span_count", "span_count" in st)
    check("17.14 stats has active_spans", "active_spans" in st)
    check("17.15 stats has completed_spans", "completed_spans" in st)
    check("17.16 stats has failover_count", "failover_count" in st)
    check("17.17 stats has recovery_count", "recovery_count" in st)
    check("17.18 stats has migration_count", "migration_count" in st)

    r = repr(ht)
    check("17.19 repr contains HATelemetry", "HATelemetry" in r)


test_ha_telemetry()

# ──────────────────────────────────────────────
# 18. HAAudit
# ──────────────────────────────────────────────
print("\n=== 18. HAAudit ===")


def test_ha_audit():
    ha = HAAudit()

    ha.record_failure("order", "node_failure", {"host": "h1"})
    ha.record_promotion("order", "i1", "i2")
    ha.record_recovery("order", success=True, details={"time_ms": 150})
    ha.record_rollback("order", "config_error", {"old_version": "1.0"})
    ha.record("config_change", "order", {"key": "val"}, operator="admin")

    trail = ha.get_audit_trail()
    check("18.1 get_audit_trail returns list", isinstance(trail, list))
    check("18.2 audit trail has entries", len(trail) >= 5)

    failure_entries = [e for e in trail if e.get("event_type") == "failure"]
    check("18.3 failure entry exists", len(failure_entries) >= 1)
    check("18.4 failure has failure_type", failure_entries[0].get("failure_type") == "node_failure")

    promotion_entries = [e for e in trail if e.get("event_type") == "promotion"]
    check("18.5 promotion entry exists", len(promotion_entries) >= 1)

    recovery_entries = [e for e in trail if e.get("event_type") == "recovery"]
    check("18.6 recovery entry exists", len(recovery_entries) >= 1)
    check("18.7 recovery has success bool", recovery_entries[0].get("success") is True)

    rollback_entries = [e for e in trail if e.get("event_type") == "rollback"]
    check("18.8 rollback entry exists", len(rollback_entries) >= 1)

    filtered = ha.get_audit_trail(service_name="order")
    check("18.9 filter by service_name works", all(e.get("service_name") == "order" for e in filtered))

    filtered_empty = ha.get_audit_trail(service_name="nonexistent")
    check("18.10 filter unknown service returns empty", len(filtered_empty) == 0)

    st = ha.get_stats()
    check("18.11 get_stats returns dict", isinstance(st, dict))
    check("18.12 stats has record_count", "record_count" in st)
    check("18.13 stats has failure_count", "failure_count" in st)
    check("18.14 stats has promotion_count", "promotion_count" in st)
    check("18.15 stats has recovery_count", "recovery_count" in st)
    check("18.16 stats has rollback_count", "rollback_count" in st)
    check("18.17 stats has event_type_distribution", "event_type_distribution" in st)

    r = repr(ha)
    check("18.18 repr contains HAAudit", "HAAudit" in r)


test_ha_audit()

# ──────────────────────────────────────────────
# 19. HADiagnostics
# ──────────────────────────────────────────────
print("\n=== 19. HADiagnostics ===")


def test_ha_diagnostics():
    hd = HADiagnostics()

    hd.record_operation("failover", "order", "success", {"duration_ms": 500})
    hd.record_operation("heartbeat_check", "order", "success", {"checked": 3})
    hd.record_operation("snapshot_create", "payment", "failed", {"error": "disk full"})
    hd.record_error("order", "timeout", "failover")
    hd.record_error("order", "connection refused", "heartbeat_check")

    ops = hd.get_operations()
    check("19.1 get_operations returns list", isinstance(ops, list))
    check("19.2 operations has entries", len(ops) >= 3)
    check("19.3 operation has operation field", "operation" in ops[0])
    check("19.4 operation has service_name", "service_name" in ops[0])
    check("19.5 operation has status", "status" in ops[0])

    errs = hd.get_errors()
    check("19.6 get_errors returns list", isinstance(errs, list))
    check("19.7 errors has entries", len(errs) >= 2)
    check("19.8 error has error field", "error" in errs[0])
    check("19.9 error has operation field", "operation" in errs[0])

    ops_filtered = hd.get_operations(service_name="order")
    check("19.10 filter operations by service", len(ops_filtered) >= 2)

    errs_filtered = hd.get_errors(service_name="order")
    check("19.11 filter errors by service", len(errs_filtered) >= 2)

    empty_ops = hd.get_operations(service_name="nonexistent")
    check("19.12 filter unknown returns empty", len(empty_ops) == 0)

    report = hd.get_performance_report()
    check("19.13 get_performance_report returns dict", isinstance(report, dict))
    check("19.14 report has total_operations", "total_operations" in report)
    check("19.15 report has success_rate", "success_rate" in report)
    check("19.16 report has total_errors", "total_errors" in report)
    check("19.17 report has operations_by_service", "operations_by_service" in report)

    hd.clear(service_name="payment")
    ops_after = hd.get_operations()
    check("19.18 clear by service removes entries", all(o.get("service_name") != "payment" for o in ops_after))

    hd.clear()
    ops_after_all = hd.get_operations()
    check("19.19 clear all empties operations", len(ops_after_all) == 0)

    st = hd.get_stats()
    check("19.20 get_stats returns dict", isinstance(st, dict))
    check("19.21 stats has operation_count", "operation_count" in st)
    check("19.22 stats has error_count", "error_count" in st)

    r = repr(hd)
    check("19.23 repr contains HADiagnostics", "HADiagnostics" in r)


test_ha_diagnostics()

# ──────────────────────────────────────────────
# 20. HAHealth
# ──────────────────────────────────────────────
print("\n=== 20. HAHealth ===")


def test_ha_health():
    hh = HAHealth()

    check("20.1 is_healthy False initially", hh.is_healthy() is False)

    hh.register_component("controller", HAController())
    hh.register_component("failover", FailoverManager())
    hh.register_component("snapshot", RegistrySnapshot())
    hh.register_component("recovery", RegistryRecovery())
    hh.register_component("cluster", ClusterRebalancer())

    check_result = asyncio.run(hh.check())
    check("20.2 check returns dict", isinstance(check_result, dict))
    check("20.3 check has ha_controller", "ha_controller" in check_result)
    check("20.4 check has failover", "failover" in check_result)
    check("20.5 check has snapshot", "snapshot" in check_result)
    check("20.6 check has recovery", "recovery" in check_result)
    check("20.7 check has cluster", "cluster" in check_result)
    check("20.8 check has overall healthy", isinstance(check_result.get("healthy"), bool))
    check("20.9 check has timestamp", "timestamp" in check_result)

    check("20.10 is_healthy True after check", hh.is_healthy() is True)

    hh2 = HAHealth()
    check_result2 = asyncio.run(hh2.check())
    check("20.11 check with no components has unhealthy", check_result2.get("ha_controller", {}).get("healthy") is False)
    check("20.12 check no components is_healthy False", check_result2.get("healthy") is False)

    st = hh.get_stats()
    check("20.13 get_stats returns dict", isinstance(st, dict))
    check("20.14 stats has check_count", "check_count" in st)
    check("20.15 stats has healthy_count", "healthy_count" in st)
    check("20.16 stats has unhealthy_count", "unhealthy_count" in st)
    check("20.17 stats has components", "components" in st)

    r = repr(hh)
    check("20.18 repr contains HAHealth", "HAHealth" in r)


test_ha_health()

# ──────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"RESULTS: {checks_passed} passed, {checks_failed} failed")
print("=" * 60)

if checks_failed > 0:
    sys.exit(1)
else:
    print("ALL CHECKS PASSED!")
    sys.exit(0)
