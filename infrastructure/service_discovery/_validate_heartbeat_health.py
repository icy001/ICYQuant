"""Comprehensive validation tests for ICYQuant service discovery
Part 1.2 (heartbeat, health, recovery).

Run with:
    python -m infrastructure.service_discovery._validate_heartbeat_health
"""

from __future__ import annotations

import asyncio
import http.server
import socket
import threading
import time

from infrastructure.service_discovery.heartbeat import HeartbeatService
from infrastructure.service_discovery.heartbeat_scheduler import HeartbeatScheduler
from infrastructure.service_discovery.lease import LeaseManager, ServiceLease
from infrastructure.service_discovery.lease_manager import AsyncLeaseManager
from infrastructure.service_discovery.probe import (
    Probe,
    ProbeResult,
    TCPProbe,
    HTTPProbe,
    GRPCProbe,
    InternalProbe,
    ProbeFactory,
)
from infrastructure.service_discovery.health_checker import HealthChecker
from infrastructure.service_discovery.health_monitor import HealthMonitor
from infrastructure.service_discovery.readiness import ReadinessProbe
from infrastructure.service_discovery.liveness import LivenessProbe
from infrastructure.service_discovery.startup import StartupProbe
from infrastructure.service_discovery.detector import PhiAccrualDetector
from infrastructure.service_discovery.quarantine import QuarantineManager
from infrastructure.service_discovery.expiration import LeaseExpiration
from infrastructure.service_discovery.recovery import ServiceRecovery
from infrastructure.service_discovery.scheduler import HealthScheduler
from infrastructure.service_discovery.telemetry import ServiceDiscoveryTelemetry
from infrastructure.service_discovery.policies import (
    HealthPolicy,
    AlwaysHealthyPolicy,
    ThresholdPolicy,
    ConsecutiveFailurePolicy,
    AdaptivePolicy,
    PolicyFactory,
)
from infrastructure.service_discovery.events import ServiceEventBus
from infrastructure.service_discovery.exceptions import ServiceDiscoveryError

checks_passed = 0
checks_failed = 0


def check(name, condition):
    global checks_passed, checks_failed
    if condition:
        checks_passed += 1
    else:
        checks_failed += 1
        print(f"  [FAIL] {name}")


# ── Test helpers ──────────────────────────────────────────────────────


class _OkHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


def _start_http_server():
    server = http.server.HTTPServer(("127.0.0.1", 0), _OkHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def _start_tcp_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    return sock, sock.getsockname()[1]


class _MockRegistry:
    """Minimal registry mock for expiration/recovery tests."""

    def __init__(self):
        self.deregistered = []
        self.restarted = []
        self.marked_healthy = []

    def deregister(self, service_name, instance_id):
        self.deregistered.append((service_name, instance_id))
        return True

    def restart(self, service_name, instance_id):
        self.restarted.append((service_name, instance_id))
        return True

    def mark_healthy(self, service_name, instance_id):
        self.marked_healthy.append((service_name, instance_id))
        return True


# ── Section 1: HeartbeatService ───────────────────────────────────────


async def test_heartbeat_service():
    print("\n=== 1. HeartbeatService ===")

    # Construction with defaults
    hs = HeartbeatService()
    check("default interval is 5.0", hs._interval == 5.0)
    check("default timeout is 15.0", hs._timeout == 15.0)
    check("no lease manager by default", hs._lease_manager is None)

    # Construction with custom params
    hs2 = HeartbeatService(interval=2.0, timeout=10.0)
    check("custom interval", hs2._interval == 2.0)
    check("custom timeout", hs2._timeout == 10.0)

    # Invalid interval falls back to 5.0
    hs3 = HeartbeatService(interval=-1, timeout=-1)
    check("invalid interval falls back to 5.0", hs3._interval == 5.0)
    check("invalid timeout falls back to 15.0", hs3._timeout == 15.0)

    # is_beating before start
    check("not beating before start", hs.is_beating("svc", "i1") is False)

    # start sends initial beat
    await hs.start("svc", "i1")
    check("is_beating after start", hs.is_beating("svc", "i1") is True)

    info = hs.get_heartbeat_info("svc", "i1")
    check("get_heartbeat_info returns dict", info is not None)
    check("heartbeat record has service_name", info["service_name"] == "svc")
    check("heartbeat record has instance_id", info["instance_id"] == "i1")
    check("initial beat_count is 1", info["beat_count"] == 1)
    check("started flag is True", info["started"] is True)
    check("last_heartbeat is set", info["last_heartbeat"] is not None)

    # Second beat increments count
    result = await hs.beat("svc", "i1")
    check("beat returns dict", isinstance(result, dict))
    check("beat_count is 2 after second beat", result["beat_count"] == 2)
    check("beat result has latency", isinstance(result.get("latency"), (int, float)))

    # get_stats
    stats = hs.get_stats()
    check("stats has interval", stats["interval"] == 5.0)
    check("stats has tracked_instances", stats["tracked_instances"] >= 1)
    check("stats has active_instances", stats["active_instances"] >= 1)
    check("stats has total_beats", stats["total_beats"] >= 2)
    check("stats has total_missed", stats["total_missed"] == 0)
    check("stats lease_manager_attached is False", stats["lease_manager_attached"] is False)

    # stop
    await hs.stop("svc", "i1")
    check("not beating after stop", hs.is_beating("svc", "i1") is False)

    # get_heartbeat_info for unknown instance
    check("unknown instance returns None", hs.get_heartbeat_info("x", "y") is None)


# ── Section 2: HeartbeatScheduler ─────────────────────────────────────


async def test_heartbeat_scheduler():
    print("\n=== 2. HeartbeatScheduler ===")

    hs = HeartbeatService()
    sched = HeartbeatScheduler(hs)

    # Construction
    check("scheduler not running initially", sched.is_running() is False)
    check("scheduler has heartbeat_service", sched._heartbeat_service is hs)

    # Jitter
    jittered = sched._apply_jitter(10.0)
    check("jitter stays within ±10%", 9.0 <= jittered <= 11.0)
    check("jitter of 0 stays 0", sched._apply_jitter(0) == 0)

    # Register
    sched.register("svc", "i1", interval=5.0)
    registered = sched.get_registered()
    check("one registered target", len(registered) == 1)
    check("registered has service_name", registered[0]["service_name"] == "svc")
    check("registered has instance_id", registered[0]["instance_id"] == "i1")
    check("registered has interval", registered[0]["interval"] == 5.0)

    # Unregister
    sched.unregister("svc", "i1")
    check("no registered after unregister", len(sched.get_registered()) == 0)

    # Start / stop
    sched.register("svc", "i1", interval=0.1)
    await sched.start()
    check("is_running after start", sched.is_running() is True)

    # Double start raises
    try:
        await sched.start()
        check("double start raises", False)
    except ServiceDiscoveryError:
        check("double start raises", True)

    # Wait for dispatches
    await asyncio.sleep(0.35)
    stats = sched.get_stats()
    check("dispatch_count > 0", stats["dispatch_count"] > 0)
    check("stats running is True", stats["running"] is True)
    check("stats registered_count >= 1", stats["registered_count"] >= 1)
    check("stats heartbeat_service_attached", stats["heartbeat_service_attached"] is True)

    await sched.stop()
    check("not running after stop", sched.is_running() is False)


# ── Section 3: AsyncLeaseManager ───────────────────────────────────────


async def test_async_lease_manager():
    print("\n=== 3. AsyncLeaseManager ===")

    mgr = AsyncLeaseManager()
    check("no event bus by default", mgr._event_bus is None)
    check("no leases initially", len(mgr.get_all_leases()) == 0)

    # create_lease
    lease = await mgr.create_lease("svc", "i1", ttl=30, renew_interval=10)
    check("create_lease returns ServiceLease", isinstance(lease, ServiceLease))
    check("lease has service_name", lease.service_name == "svc")
    check("lease has instance_id", lease.instance_id == "i1")
    check("lease ttl is 30", lease.ttl == 30)
    check("lease not expired", lease.is_expired() is False)

    # get_lease
    fetched = mgr.get_lease("svc", "i1")
    check("get_lease returns lease", fetched is not None)
    check("get_lease returns same lease", fetched is lease)

    # renew_lease
    renewed = await mgr.renew_lease("svc", "i1")
    check("renew_lease returns lease", renewed is not None)
    check("renew_lease returns ServiceLease", isinstance(renewed, ServiceLease))

    # renew non-existent
    renewed_none = await mgr.renew_lease("x", "y")
    check("renew non-existent returns None", renewed_none is None)

    # check_leases
    counts = await mgr.check_leases()
    check("check_leases has total", counts["total"] == 1)
    check("check_leases has active", counts["active"] == 1)
    check("check_leases has expired", counts["expired"] == 0)

    # get_all_leases
    all_leases = mgr.get_all_leases()
    check("get_all_leases returns list", isinstance(all_leases, list))
    check("get_all_leases has 1 entry", len(all_leases) == 1)
    check("lease dict has ttl", all_leases[0]["ttl"] == 30)

    # get_stats
    stats = mgr.get_stats()
    check("stats has total_leases", stats["total_leases"] == 1)
    check("stats has active_leases", stats["active_leases"] == 1)
    check("stats has created_total", stats["created_total"] >= 1)
    check("stats has renewed_total", stats["renewed_total"] >= 1)
    check("stats event_bus_attached is False", stats["event_bus_attached"] is False)

    # expire_lease
    exp_result = await mgr.expire_lease("svc", "i1")
    check("expire_lease returns dict", isinstance(exp_result, dict))
    check("expire_lease expired is True", exp_result["expired"] is True)
    check("lease removed after expire", mgr.get_lease("svc", "i1") is None)

    # cleanup_expired
    await mgr.create_lease("svc2", "i1", ttl=1, renew_interval=1)
    cleaned = await mgr.cleanup_expired()
    check("cleanup_expired returns int", isinstance(cleaned, int))
    check("cleanup_expired >= 0", cleaned >= 0)


# ── Section 4: Probes ─────────────────────────────────────────────────


async def test_probes():
    print("\n=== 4. Probe (TCPProbe, HTTPProbe, InternalProbe) ===")

    # ProbeResult dataclass
    pr = ProbeResult(
        success=True,
        status="ok",
        latency_ms=12.5,
        message="ok",
    )
    check("ProbeResult success", pr.success is True)
    check("ProbeResult status", pr.status == "ok")
    check("ProbeResult latency_ms", pr.latency_ms == 12.5)
    pr_dict = pr.to_dict()
    check("ProbeResult.to_dict has success", pr_dict["success"] is True)
    check("ProbeResult.to_dict has status", pr_dict["status"] == "ok")
    check("ProbeResult.to_dict has timestamp", pr_dict["timestamp"] is not None)
    check("ProbeResult.to_dict has details", isinstance(pr_dict["details"], dict))

    # TCPProbe - parse_target
    check("parse host:port", TCPProbe._parse_target("localhost:8080") == ("localhost", 8080))
    check("parse host only", TCPProbe._parse_target("localhost") == ("localhost", 80))
    check("parse empty", TCPProbe._parse_target("") == ("localhost", 80))
    check("parse invalid port", TCPProbe._parse_target("host:abc") == ("host:abc", 80))

    # TCPProbe - failure (unreachable port)
    tcp = TCPProbe(timeout=0.5)
    fail_result = await tcp.execute("127.0.0.1:1")
    check("TCPProbe failure success is False", fail_result["success"] is False)
    check("TCPProbe failure status", fail_result["status"] == "failed")
    check("TCPProbe failure has latency_ms", "latency_ms" in fail_result)
    check("TCPProbe failure has message", isinstance(fail_result["message"], str))

    # TCPProbe - success (local server)
    sock, port = _start_tcp_server()
    try:
        tcp2 = TCPProbe(timeout=2.0)
        ok_result = await tcp2.execute(f"127.0.0.1:{port}")
        check("TCPProbe success is True", ok_result["success"] is True)
        check("TCPProbe success status", ok_result["status"] == "ok")
    finally:
        sock.close()

    # TCPProbe get_stats
    tcp_stats = tcp.get_stats()
    check("TCPProbe stats probe_type", tcp_stats["probe_type"] == "tcp")
    check("TCPProbe stats exec_count", tcp_stats["exec_count"] >= 1)
    check("TCPProbe stats failure_count", tcp_stats["failure_count"] >= 1)

    # HTTPProbe - failure
    http_probe = HTTPProbe(timeout=0.5)
    http_fail = await http_probe.execute("http://127.0.0.1:1/health")
    check("HTTPProbe failure success is False", http_fail["success"] is False)
    check("HTTPProbe failure status", http_fail["status"] == "failed")

    # HTTPProbe - success (local server)
    server, hport = _start_http_server()
    try:
        http_probe2 = HTTPProbe(timeout=2.0)
        http_ok = await http_probe2.execute(f"http://127.0.0.1:{hport}/health")
        check("HTTPProbe success is True", http_ok["success"] is True)
        check("HTTPProbe success status", http_ok["status"] == "ok")
    finally:
        server.shutdown()

    # InternalProbe - no check_fn
    empty_probe = InternalProbe()
    empty_result = await empty_probe.execute("internal")
    check("InternalProbe no fn success is False", empty_result["success"] is False)

    # InternalProbe - sync True
    sync_probe = InternalProbe(check_fn=lambda: True)
    sync_ok = await sync_probe.execute("internal")
    check("InternalProbe sync True succeeds", sync_ok["success"] is True)

    # InternalProbe - sync False
    false_probe = InternalProbe(check_fn=lambda: False)
    false_result = await false_probe.execute("internal")
    check("InternalProbe sync False fails", false_result["success"] is False)

    # InternalProbe - dict result
    dict_probe = InternalProbe(check_fn=lambda: {"success": True, "message": "ok"})
    dict_result = await dict_probe.execute("internal")
    check("InternalProbe dict result succeeds", dict_result["success"] is True)

    # InternalProbe - raises
    def raise_fn():
        raise RuntimeError("boom")

    raise_probe = InternalProbe(check_fn=raise_fn)
    raise_result = await raise_probe.execute("internal")
    check("InternalProbe raising fn fails", raise_result["success"] is False)

    # InternalProbe - async check_fn
    async def async_check():
        return True

    async_probe = InternalProbe(check_fn=async_check)
    async_result = await async_probe.execute("internal")
    check("InternalProbe async fn succeeds", async_result["success"] is True)

    # InternalProbe get_stats
    ip_stats = async_probe.get_stats()
    check("InternalProbe stats probe_type", ip_stats["probe_type"] == "internal")
    check("InternalProbe stats check_fn_set", ip_stats["check_fn_set"] is True)

    # ProbeFactory
    check("ProbeFactory creates TCPProbe", isinstance(ProbeFactory.create("tcp"), TCPProbe))
    check("ProbeFactory creates HTTPProbe", isinstance(ProbeFactory.create("http"), HTTPProbe))
    check("ProbeFactory creates GRPCProbe", isinstance(ProbeFactory.create("grpc"), GRPCProbe))
    check("ProbeFactory creates InternalProbe", isinstance(ProbeFactory.create("internal"), InternalProbe))
    try:
        ProbeFactory.create("unknown")
        check("ProbeFactory unknown raises ValueError", False)
    except ValueError:
        check("ProbeFactory unknown raises ValueError", True)


# ── Section 5: HealthChecker ──────────────────────────────────────────


async def test_health_checker():
    print("\n=== 5. HealthChecker ===")

    hc = HealthChecker(default_timeout=0.5)
    check("default_timeout set", hc._default_timeout == 0.5)

    # Default probes registered
    stats = hc.get_stats()
    check("has tcp probe", "tcp" in stats["registered_probes"])
    check("has http probe", "http" in stats["registered_probes"])
    check("has grpc probe", "grpc" in stats["registered_probes"])

    # get_probe
    tcp_probe = hc.get_probe("tcp")
    check("get_probe tcp returns TCPProbe", isinstance(tcp_probe, TCPProbe))
    http_probe = hc.get_probe("http")
    check("get_probe http returns HTTPProbe", isinstance(http_probe, HTTPProbe))

    # check_tcp failure
    tcp_fail = await hc.check_tcp("127.0.0.1", 1, timeout=0.5)
    check("check_tcp failure success is False", tcp_fail["success"] is False)

    # check_tcp success
    sock, port = _start_tcp_server()
    try:
        tcp_ok = await hc.check_tcp("127.0.0.1", port, timeout=2.0)
        check("check_tcp success is True", tcp_ok["success"] is True)
    finally:
        sock.close()

    # check_http failure
    http_fail = await hc.check_http("http://127.0.0.1:1/h", timeout=0.5)
    check("check_http failure success is False", http_fail["success"] is False)

    # check_internal
    int_ok = await hc.check_internal(lambda: True)
    check("check_internal success is True", int_ok["success"] is True)
    int_fail = await hc.check_internal(lambda: False)
    check("check_internal failure is False", int_fail["success"] is False)

    # register_custom_probe
    custom = InternalProbe(check_fn=lambda: True)
    hc.register_custom_probe("custom", custom)
    check("custom probe registered", hc.get_probe("custom") is custom)

    # register_custom_probe with non-Probe raises
    try:
        hc.register_custom_probe("bad", "not_a_probe")
        check("register non-Probe raises", False)
    except ServiceDiscoveryError:
        check("register non-Probe raises", True)

    # get_probe with unknown name creates via factory
    new_probe = hc.get_probe("tcp")
    check("get_probe fallback works", new_probe is not None)

    # get_probe with invalid name raises
    try:
        hc.get_probe("nonexistent_probes")
        check("get_probe invalid raises", False)
    except ServiceDiscoveryError:
        check("get_probe invalid raises", True)

    # check() method
    outcome = await hc.check("svc", "i1", probe_type="internal")
    check("check returns outcome dict", isinstance(outcome, dict))
    check("outcome has service_name", outcome["service_name"] == "svc")
    check("outcome has instance_id", outcome["instance_id"] == "i1")
    check("outcome has probe_type", outcome["probe_type"] == "internal")
    check("outcome has result", isinstance(outcome["result"], dict))
    check("outcome has checked_at", "checked_at" in outcome)

    # get_stats after checks
    final_stats = hc.get_stats()
    check("stats check_count > 0", final_stats["check_count"] > 0)
    check("stats has probes dict", isinstance(final_stats["probes"], dict))


# ── Section 6: HealthMonitor ──────────────────────────────────────────


async def test_health_monitor():
    print("\n=== 6. HealthMonitor ===")

    hc = HealthChecker(default_timeout=0.5)
    # Register an internal probe that returns True
    hc.register_custom_probe("internal_ok", InternalProbe(check_fn=lambda: True))
    hc.register_custom_probe("internal_fail", InternalProbe(check_fn=lambda: False))

    hm = HealthMonitor(hc)
    check("monitor not running initially", hm._running is False)

    # start
    await hm.start()
    check("monitor running after start", hm._running is True)

    # double start raises
    try:
        await hm.start()
        check("double start raises", False)
    except ServiceDiscoveryError:
        check("double start raises", True)

    # monitor an instance with passing probe
    await hm.monitor("svc", "i1", probe_type="internal_ok", interval=0.1)
    health = hm.get_health("svc", "i1")
    check("get_health returns dict", health is not None)
    check("health has service_name", health["service_name"] == "svc")
    check("health monitoring flag", health["monitoring"] is True)
    check("health probe_type", health["probe_type"] == "internal_ok")
    check("is_healthy initially True", hm.is_healthy("svc", "i1") is True)

    # Wait for checks to run
    await asyncio.sleep(0.25)
    health_after = hm.get_health("svc", "i1")
    check("check_count > 0 after monitoring", health_after["check_count"] > 0)
    check("still healthy with passing probe", hm.is_healthy("svc", "i1") is True)

    # monitor with failing probe
    await hm.monitor("svc", "i2", probe_type="internal_fail", interval=0.1)
    await asyncio.sleep(0.25)
    check("unhealthy with failing probe", hm.is_healthy("svc", "i2") is False)

    # get_all_health
    all_health = hm.get_all_health()
    check("get_all_health returns dict", isinstance(all_health, dict))
    check("get_all_health has entries", len(all_health) >= 2)

    # get_unhealthy
    unhealthy = hm.get_unhealthy()
    check("get_unhealthy returns list", isinstance(unhealthy, list))
    check("get_unhealthy has i2", any(r["instance_id"] == "i2" for r in unhealthy))

    # get_stats
    stats = hm.get_stats()
    check("stats running is True", stats["running"] is True)
    check("stats monitored_count >= 2", stats["monitored_count"] >= 2)
    check("stats total_checks > 0", stats["total_checks"] > 0)

    # unmonitor
    hm.unmonitor("svc", "i1")
    check("unmonitored not monitoring", hm.get_health("svc", "i1")["monitoring"] is False)

    # stop
    await hm.stop()
    check("monitor not running after stop", hm._running is False)


# ── Section 7: ReadinessProbe ─────────────────────────────────────────


async def test_readiness_probe():
    print("\n=== 7. ReadinessProbe ===")

    rp = ReadinessProbe()
    check("not ready initially", rp.is_ready() is False)
    check("no checks initially", len(rp.get_checks()) == 0)
    check("DEFAULT_CHECKS has database", "database" in ReadinessProbe.DEFAULT_CHECKS)
    check("DEFAULT_CHECKS has redis", "redis" in ReadinessProbe.DEFAULT_CHECKS)

    # add_check
    rp.add_check("db", lambda: True)
    rp.add_check("redis", lambda: True)
    stats = rp.get_stats()
    check("stats check_count is 2", stats["check_count"] == 2)
    check("stats has check_names", len(stats["check_names"]) == 2)

    # add_check with empty name raises
    try:
        rp.add_check("", lambda: True)
        check("add_check empty name raises", False)
    except ServiceDiscoveryError:
        check("add_check empty name raises", True)

    # add_check with non-callable raises
    try:
        rp.add_check("bad", "not_callable")
        check("add_check non-callable raises", False)
    except ServiceDiscoveryError:
        check("add_check non-callable raises", True)

    # execute - all pass
    result = await rp.execute()
    check("execute ready is True", result["ready"] is True)
    check("execute status is ready", result["status"] == "ready")
    check("execute has checks dict", isinstance(result["checks"], dict))
    check("execute has latency_ms", "latency_ms" in result)
    check("is_ready after passing", rp.is_ready() is True)

    # add failing check
    rp.add_check("kafka", lambda: False)
    result2 = await rp.execute()
    check("execute not ready with failure", result2["ready"] is False)
    check("execute status is not_ready", result2["status"] == "not_ready")
    check("is_ready after failing", rp.is_ready() is False)
    check("failing check recorded", result2["checks"]["kafka"] is False)

    # remove_check
    rp.remove_check("kafka")
    result3 = await rp.execute()
    check("ready after removing failing check", result3["ready"] is True)

    # execute with raising check
    rp.add_check("boom", lambda: (_ for _ in ()).throw(RuntimeError("err")))
    result4 = await rp.execute()
    check("raising check marks not ready", result4["ready"] is False)
    check("raising check has error", "boom" in result4.get("errors", {}))

    # construction with initial checks
    def check_a():
        return True

    rp2 = ReadinessProbe(checks=[check_a])
    check("ReadinessProbe with initial checks", len(rp2.get_stats()["check_names"]) == 1)


# ── Section 8: LivenessProbe ──────────────────────────────────────────


async def test_liveness_probe():
    print("\n=== 8. LivenessProbe ===")

    lp = LivenessProbe()
    check("alive initially True", lp.is_alive() is True)
    check("no checks initially", lp.get_stats()["check_count"] == 0)
    check("DEFAULT_CHECKS has deadlock", "deadlock" in LivenessProbe.DEFAULT_CHECKS)
    check("DEFAULT_CHECKS has heartbeat", "heartbeat" in LivenessProbe.DEFAULT_CHECKS)

    # add_check
    lp.add_check("deadlock", lambda: True)
    lp.add_check("memory", lambda: True)
    check("check_count is 2", lp.get_stats()["check_count"] == 2)

    # add_check validation
    try:
        lp.add_check("", lambda: True)
        check("add_check empty name raises", False)
    except ServiceDiscoveryError:
        check("add_check empty name raises", True)

    try:
        lp.add_check("bad", 123)
        check("add_check non-callable raises", False)
    except ServiceDiscoveryError:
        check("add_check non-callable raises", True)

    # execute - all pass
    result = await lp.execute()
    check("execute alive is True", result["alive"] is True)
    check("execute status is alive", result["status"] == "alive")
    check("execute has checks dict", isinstance(result["checks"], dict))
    check("execute has timestamp", "timestamp" in result)
    check("is_alive after passing", lp.is_alive() is True)
    check("failure_count is 0", lp.get_stats()["failure_count"] == 0)

    # add failing check
    lp.add_check("thread", lambda: False)
    result2 = await lp.execute()
    check("execute alive is False with failure", result2["alive"] is False)
    check("execute status is dead", result2["status"] == "dead")
    check("is_alive after failing", lp.is_alive() is False)
    check("failure_count is 1", lp.get_stats()["failure_count"] == 1)

    # is_alive stays False until next execute (no remove_check on LivenessProbe)
    check("is_alive stays False after failing", lp.is_alive() is False)

    # replace failing check with passing one via internal dict
    with lp._lock:
        lp._checks["thread"] = lambda: True
    result_recover = await lp.execute()
    check("execute alive True after recovery", result_recover["alive"] is True)

    # execute with raising check
    lp2 = LivenessProbe()
    lp2.add_check("raise", lambda: (_ for _ in ()).throw(ValueError("err")))
    result3 = await lp2.execute()
    check("raising check marks dead", result3["alive"] is False)
    check("raising check has error", "raise" in result3.get("errors", {}))

    # get_stats
    stats = lp.get_stats()
    check("stats has python_version", "python_version" in stats)
    check("stats has last_results", isinstance(stats["last_results"], dict))


# ── Section 9: StartupProbe ───────────────────────────────────────────


async def test_startup_probe():
    print("\n=== 9. StartupProbe ===")

    sp = StartupProbe(timeout=300.0, check_interval=5.0)
    check("not started initially", sp.is_started() is False)
    check("timeout is 300", sp._timeout == 300.0)
    check("check_interval is 5", sp._check_interval == 5.0)

    # execute with no checks - not started, not timed out
    result = await sp.execute()
    check("execute started is False", result["started"] is False)
    check("execute timed_out is False", result["timed_out"] is False)
    check("execute status is starting", result["status"] == "starting")
    check("is_started still False", sp.is_started() is False)

    # add_check
    sp.add_check("init", lambda: True)
    check("check added", sp.get_stats()["check_count"] == 1)

    # add_check validation
    try:
        sp.add_check("", lambda: True)
        check("add_check empty name raises", False)
    except ServiceDiscoveryError:
        check("add_check empty name raises", True)

    # execute with passing checks - started
    result2 = await sp.execute()
    check("execute started with passing checks", result2["started"] is True)
    check("execute status is started", result2["status"] == "started")
    check("is_started after passing", sp.is_started() is True)

    # execute again - already started
    result3 = await sp.execute()
    check("already started returns started", result3["started"] is True)
    check("already started message", "already" in result3["message"].lower())

    # mark_started on fresh probe
    sp2 = StartupProbe(timeout=300.0)
    sp2.mark_started()
    check("is_started after mark_started", sp2.is_started() is True)
    result4 = await sp2.execute()
    check("execute after mark returns started", result4["started"] is True)

    # timeout test
    sp3 = StartupProbe(timeout=0.1, check_interval=0.05)
    sp3.add_check("slow", lambda: False)
    await asyncio.sleep(0.2)
    result5 = await sp3.execute()
    check("execute timed_out is True", result5["timed_out"] is True)
    check("execute started is False", result5["started"] is False)
    check("execute status is timed_out", result5["status"] == "timed_out")

    # reset
    sp3.reset()
    check("is_started False after reset", sp3.is_started() is False)
    check("exec_count 0 after reset", sp3.get_stats()["exec_count"] == 0)

    # get_stats
    stats = sp.get_stats()
    check("stats has started", "started" in stats)
    check("stats has timeout", "timeout" in stats)
    check("stats has check_count", "check_count" in stats)
    check("stats has elapsed_seconds", "elapsed_seconds" in stats)

    # construction with initial checks
    def init_check():
        return True

    sp4 = StartupProbe(checks=[init_check])
    check("StartupProbe with initial checks", sp4.get_stats()["check_count"] == 1)


# ── Section 10: PhiAccrualDetector ────────────────────────────────────


def test_phi_accrual_detector():
    print("\n=== 10. PhiAccrualDetector ===")

    # Construction
    det = PhiAccrualDetector(threshold=8.0, min_samples=10, max_samples=1000)
    check("threshold is 8.0", det._threshold == 8.0)
    check("min_samples is 10", det._min_samples == 10)
    check("max_samples is 1000", det._max_samples == 1000)
    check("STATE_ALIVE constant", det.STATE_ALIVE == "ALIVE")
    check("STATE_SUSPICIOUS constant", det.STATE_SUSPICIOUS == "SUSPICIOUS")
    check("STATE_DEAD constant", det.STATE_DEAD == "DEAD")

    # compute_phi before any heartbeat
    phi = det.compute_phi("svc", "i1")
    check("phi is 0 before heartbeat", phi == 0.0)
    check("is_suspicious False before heartbeat", det.is_suspicious("svc", "i1") is False)
    check("is_failed False before heartbeat", det.is_failed("svc", "i1") is False)
    check("get_state is ALIVE before heartbeat", det.get_state("svc", "i1") == "ALIVE")

    # record heartbeats
    det.record_heartbeat("svc", "i1")
    check("record_count is 1", det._record_count == 1)
    det.record_heartbeat("svc", "i1")
    check("record_count is 2", det._record_count == 2)

    # Immediately after heartbeat, phi should be small
    phi_recent = det.compute_phi("svc", "i1")
    check("phi small after recent heartbeat", phi_recent < 8.0)
    check("is_suspicious False after recent", det.is_suspicious("svc", "i1") is False)
    check("get_state ALIVE after recent", det.get_state("svc", "i1") == "ALIVE")

    # Conservative path: not enough samples, long delay → suspicious
    det_susp = PhiAccrualDetector(threshold=0.5, min_samples=1000)
    det_susp.record_heartbeat("svc", "i1")
    time.sleep(0.7)
    phi_susp = det_susp.compute_phi("svc", "i1")
    check("phi >= 0.5 after delay (conservative)", phi_susp >= 0.5)
    check("is_suspicious True after delay", det_susp.is_suspicious("svc", "i1") is True)
    check("is_failed False at 0.7s (conservative)", det_susp.is_failed("svc", "i1") is False)
    check("get_state SUSPICIOUS", det_susp.get_state("svc", "i1") == "SUSPICIOUS")

    # Conservative path: longer delay → dead
    det_dead = PhiAccrualDetector(threshold=0.1, min_samples=1000)
    det_dead.record_heartbeat("svc", "i1")
    time.sleep(0.3)
    phi_dead = det_dead.compute_phi("svc", "i1")
    check("phi >= 0.2 after 0.3s delay", phi_dead >= 0.2)
    check("is_failed True after long delay", det_dead.is_failed("svc", "i1") is True)
    check("get_state DEAD", det_dead.get_state("svc", "i1") == "DEAD")

    # Enough samples path
    det_samples = PhiAccrualDetector(threshold=8.0, min_samples=2, max_samples=100)
    for _ in range(5):
        det_samples.record_heartbeat("svc", "i2")
        time.sleep(0.01)
    phi_samples = det_samples.compute_phi("svc", "i2")
    check("phi computed with enough samples", phi_samples >= 0.0)
    check("is_suspicious False with recent samples", det_samples.is_suspicious("svc", "i2") is False)

    # reset
    det_samples.reset("svc", "i2")
    check("reset_count incremented", det_samples._reset_count >= 1)
    check("phi is 0 after reset", det_samples.compute_phi("svc", "i2") == 0.0)

    # get_stats
    stats = det.get_stats()
    check("stats has threshold", stats["threshold"] == 8.0)
    check("stats has tracked_instances", "tracked_instances" in stats)
    check("stats has record_count", stats["record_count"] >= 2)
    check("stats has by_state", isinstance(stats["by_state"], dict))
    check("stats by_state has ALIVE", "ALIVE" in stats["by_state"])


# ── Section 11: QuarantineManager ─────────────────────────────────────


def test_quarantine_manager():
    print("\n=== 11. QuarantineManager ===")

    qm = QuarantineManager(auto_release_ttl=300.0)
    check("no quarantined initially", len(qm.get_quarantined()) == 0)
    check("is_quarantined False initially", qm.is_quarantined("svc", "i1") is False)
    check("auto_release_ttl is 300", qm._auto_release_ttl == 300.0)

    # quarantine
    record = qm.quarantine("svc", "i1", reason="unhealthy")
    check("quarantine returns dict", isinstance(record, dict))
    check("quarantine record has service_name", record["service_name"] == "svc")
    check("quarantine record has reason", record["reason"] == "unhealthy")
    check("quarantine record released is False", record["released"] is False)
    check("quarantine record has quarantined_at", record["quarantined_at"] > 0)
    check("quarantine record has expires_at", record["expires_at"] > 0)

    # is_quarantined
    check("is_quarantined True after quarantine", qm.is_quarantined("svc", "i1") is True)

    # get_quarantined
    quarantined = qm.get_quarantined()
    check("get_quarantined has 1 entry", len(quarantined) == 1)
    check("get_quarantined entry is dict", isinstance(quarantined[0], dict))

    # get_quarantine_info
    info = qm.get_quarantine_info("svc", "i1")
    check("get_quarantine_info returns dict", info is not None)
    check("get_quarantine_info reason", info["reason"] == "unhealthy")
    check("get_quarantine_info unknown returns None", qm.get_quarantine_info("x", "y") is None)

    # quarantine second instance
    qm.quarantine("svc", "i2", reason="timeout")
    check("two quarantined", len(qm.get_quarantined()) == 2)

    # release
    release_result = qm.release("svc", "i1")
    check("release returns dict", isinstance(release_result, dict))
    check("release released is True", release_result["released"] is True)
    check("release has released_at", release_result["released_at"] is not None)
    check("is_quarantined False after release", qm.is_quarantined("svc", "i1") is False)
    check("one quarantined after release", len(qm.get_quarantined()) == 1)

    # release non-quarantined
    release_none = qm.release("x", "y")
    check("release non-quarantined released is False", release_none["released"] is False)

    # get_stats
    stats = qm.get_stats()
    check("stats quarantined_count is 1", stats["quarantined_count"] == 1)
    check("stats quarantine_total is 2", stats["quarantine_total"] == 2)
    check("stats release_total is 1", stats["release_total"] >= 1)
    check("stats has auto_release_ttl", stats["auto_release_ttl"] == 300.0)

    # release_expired with short TTL
    qm2 = QuarantineManager(auto_release_ttl=0.1)
    qm2.quarantine("svc", "i1", reason="test")
    time.sleep(0.15)
    released_count = qm2.release_expired()
    check("release_expired returns 1", released_count == 1)
    check("auto-released instance no longer quarantined", qm2.is_quarantined("svc", "i1") is False)

    # release_expired with TTL=0 (disabled)
    qm3 = QuarantineManager(auto_release_ttl=0)
    qm3.quarantine("svc", "i1")
    check("release_expired returns 0 when disabled", qm3.release_expired() == 0)


# ── Section 12: LeaseExpiration ───────────────────────────────────────


async def test_lease_expiration():
    print("\n=== 12. LeaseExpiration ===")

    mgr = AsyncLeaseManager()
    registry = _MockRegistry()
    bus = ServiceEventBus()
    exp = LeaseExpiration(mgr, registry=registry, event_bus=bus)

    check("expiration has lease_manager", exp._lease_manager is mgr)
    check("expiration has registry", exp._registry is registry)
    check("expiration has event_bus", exp._event_bus is bus)

    # check_expirations with no leases
    counts = await exp.check_expirations()
    check("check_expirations total is 0", counts["total"] == 0)
    check("check_expirations active is 0", counts["active"] == 0)
    check("check_expirations expired is 0", counts["expired"] == 0)

    # Create a lease
    await mgr.create_lease("svc", "i1", ttl=30, renew_interval=10)
    counts2 = await exp.check_expirations()
    check("check_expirations total is 1", counts2["total"] == 1)
    check("check_expirations active is 1", counts2["active"] == 1)

    # expire_lease on existing
    result = await exp.expire_lease("svc", "i1")
    check("expire_lease returns dict", isinstance(result, dict))
    check("expire_lease expired is True", result["expired"] is True)
    check("expire_lease registry_removed is True", result["registry_removed"] is True)
    check("expire_lease event_published is True", result["event_published"] is True)
    check("expire_lease has timestamp", "timestamp" in result)
    check("registry deregistered called", len(registry.deregistered) == 1)

    # lease removed after expiration
    check("lease removed after expire", mgr.get_lease("svc", "i1") is None)

    # expire_lease on non-existent
    result_none = await exp.expire_lease("x", "y")
    check("expire non-existent expired is False", result_none["expired"] is False)
    check("expire non-existent has message", "message" in result_none)

    # process_expired with no expired leases
    empty_result = await exp.process_expired()
    check("process_expired returns empty list", empty_result == [])

    # Create expired lease and process
    await mgr.create_lease("svc2", "i1", ttl=1, renew_interval=1)
    await mgr.expire_lease("svc2", "i1")  # explicitly expire
    # After explicit expire, lease is removed from manager, so get_expired_leases returns []
    processed = await exp.process_expired()
    check("process_expired returns list", isinstance(processed, list))

    # get_expiration_stats
    exp_stats = exp.get_expiration_stats()
    check("expiration stats has check_count", exp_stats["check_count"] >= 2)
    check("expiration stats has expired_count", exp_stats["expired_count"] >= 1)
    check("expiration stats has history_size", exp_stats["history_size"] >= 1)

    # get_stats
    stats = exp.get_stats()
    check("stats registry_attached is True", stats["registry_attached"] is True)
    check("stats event_bus_attached is True", stats["event_bus_attached"] is True)
    check("stats has check_count", "check_count" in stats)


# ── Section 13: ServiceRecovery ───────────────────────────────────────


async def test_service_recovery():
    print("\n=== 13. ServiceRecovery ===")

    sr = ServiceRecovery(max_attempts=3, backoff_base=1.01)
    check("max_attempts is 3", sr._max_attempts == 3)
    check("backoff_base is 1.01", sr._backoff_base == 1.01)
    check("not recovering initially", sr.is_recovering("svc", "i1") is False)
    check("no lease_manager", sr._lease_manager is None)
    check("no registry", sr._registry is None)

    # recover with no dependencies - should succeed
    result = await sr.recover("svc", "i1")
    check("recover returns dict", isinstance(result, dict))
    check("recover recovered is True", result["recovered"] is True)
    check("recover has attempts", result.get("attempts", 1) >= 1)
    check("not recovering after recover", sr.is_recovering("svc", "i1") is False)

    # get_recovery_history
    history = sr.get_recovery_history()
    check("history has 1 entry", len(history) == 1)
    check("history entry has service_name", history[0].get("service_name") == "svc")

    # get_recovery_history filtered by service
    history_filtered = sr.get_recovery_history("svc")
    check("history filtered has 1 entry", len(history_filtered) == 1)
    history_other = sr.get_recovery_history("other")
    check("history other is empty", len(history_other) == 0)

    # attempt_recovery
    attempt_result = await sr.attempt_recovery("svc", "i2")
    check("attempt_recovery returns dict", isinstance(attempt_result, dict))
    check("attempt_recovery has stages", isinstance(attempt_result["stages"], dict))
    check("attempt_recovery has restart stage", "restart" in attempt_result["stages"])
    check("attempt_recovery has heartbeat_resume stage", "heartbeat_resume" in attempt_result["stages"])
    check("attempt_recovery has lease_recreate stage", "lease_recreate" in attempt_result["stages"])
    check("attempt_recovery has registry_update stage", "registry_update" in attempt_result["stages"])
    check("attempt_recovery recovered is True", attempt_result["recovered"] is True)
    check("attempt_recovery has latency_ms", "latency_ms" in attempt_result)

    # recover with lease_manager
    mgr = AsyncLeaseManager()
    sr2 = ServiceRecovery(lease_manager=mgr, max_attempts=2, backoff_base=1.01)
    result2 = await sr2.recover("svc", "i3")
    check("recover with lease_manager succeeds", result2["recovered"] is True)

    # recover with registry that has restart hook
    registry = _MockRegistry()
    sr3 = ServiceRecovery(registry=registry, max_attempts=1)
    result3 = await sr3.recover("svc", "i4")
    check("recover with registry succeeds", result3["recovered"] is True)
    check("registry restart called", len(registry.restarted) == 1)
    check("registry mark_healthy called", len(registry.marked_healthy) == 1)

    # get_stats
    stats = sr.get_stats()
    check("stats has in_progress_count", stats["in_progress_count"] == 0)
    check("stats has attempt_count", stats["attempt_count"] >= 1)
    check("stats has success_count", stats["success_count"] >= 1)
    check("stats has history_size", stats["history_size"] >= 1)
    check("stats has max_attempts", stats["max_attempts"] == 3)
    check("stats lease_manager_attached is False", stats["lease_manager_attached"] is False)


# ── Section 14: HealthScheduler ───────────────────────────────────────


async def test_health_scheduler():
    print("\n=== 14. HealthScheduler ===")

    sched = HealthScheduler()
    check("not running initially", sched.is_running() is False)
    check("no tasks initially", len(sched.get_tasks()) == 0)

    # add_task
    counter = [0]

    def count_fn():
        counter[0] += 1
        return counter[0]

    sched.add_task("counter", count_fn, 0.1)
    tasks = sched.get_tasks()
    check("one task registered", len(tasks) == 1)
    check("task has name", tasks[0]["name"] == "counter")
    check("task has interval", tasks[0]["interval"] == 0.1)
    check("task has exec_count", tasks[0]["exec_count"] == 0)

    # add_task validation
    try:
        sched.add_task("", count_fn, 1.0)
        check("add_task empty name raises", False)
    except ServiceDiscoveryError:
        check("add_task empty name raises", True)

    try:
        sched.add_task("bad", "not_callable", 1.0)
        check("add_task non-callable raises", False)
    except ServiceDiscoveryError:
        check("add_task non-callable raises", True)

    # add second task
    sched.add_task("noop", lambda: None, 1.0)
    check("two tasks registered", len(sched.get_tasks()) == 2)

    # remove_task
    sched.remove_task("noop")
    check("one task after remove", len(sched.get_tasks()) == 1)
    check("removed task gone", all(t["name"] != "noop" for t in sched.get_tasks()))

    # start
    await sched.start()
    check("is_running after start", sched.is_running() is True)

    # double start raises
    try:
        await sched.start()
        check("double start raises", False)
    except ServiceDiscoveryError:
        check("double start raises", True)

    # Wait for task execution
    await asyncio.sleep(0.35)
    check("counter incremented", counter[0] >= 1)

    # run_task (immediate execution)
    val = await sched.run_task("counter")
    check("run_task returns value", val is not None)

    # run_task with unknown task
    try:
        await sched.run_task("nonexistent")
        check("run_task unknown raises", False)
    except ServiceDiscoveryError:
        check("run_task unknown raises", True)

    # get_stats
    stats = sched.get_stats()
    check("stats running is True", stats["running"] is True)
    check("stats task_count is 1", stats["task_count"] == 1)
    check("stats has exec_count dict", isinstance(stats["exec_count"], dict))
    check("stats exec_count has counter", "counter" in stats["exec_count"])

    # stop
    await sched.stop()
    check("not running after stop", sched.is_running() is False)

    # DEFAULT_TASKS
    check("DEFAULT_TASKS has heartbeat_check", any(n == "heartbeat_check" for n, _ in HealthScheduler.DEFAULT_TASKS))
    check("DEFAULT_TASKS has health_check", any(n == "health_check" for n, _ in HealthScheduler.DEFAULT_TASKS))
    check("DEFAULT_TASKS has lease_cleanup", any(n == "lease_cleanup" for n, _ in HealthScheduler.DEFAULT_TASKS))

    # register_defaults
    sched2 = HealthScheduler(register_defaults=True)
    check("defaults registered", len(sched2.get_tasks()) == 5)


# ── Section 15: ServiceDiscoveryTelemetry ─────────────────────────────


def test_telemetry():
    print("\n=== 15. ServiceDiscoveryTelemetry ===")

    tel = ServiceDiscoveryTelemetry(max_spans=1000)
    check("max_spans is 1000", tel._max_spans == 1000)
    check("no open spans initially", len(tel._open_spans) == 0)
    check("no completed spans initially", len(tel._spans) == 0)

    # record_heartbeat
    tel.record_heartbeat("svc", "i1", latency=0.05, success=True)
    tel.record_heartbeat("svc", "i1", latency=0.10, success=False)
    stats = tel.get_stats()
    check("heartbeat_total counter set", stats["counters"].get("heartbeat_total", {}).get("svc", 0) == 2)
    check("heartbeat_success_total is 1", stats["counters"].get("heartbeat_success_total", {}).get("svc", 0) == 1)
    check("heartbeat_failure_total is 1", stats["counters"].get("heartbeat_failure_total", {}).get("svc", 0) == 1)
    check("heartbeat_latency_ms recorded", "heartbeat_latency_ms" in stats["latencies"])

    # record_health_check
    tel.record_health_check("svc", "i1", probe_type="tcp", latency=0.02, success=True)
    tel.record_health_check("svc", "i2", probe_type="http", latency=0.03, success=False)
    stats2 = tel.get_stats()
    check("health_check_total is 2", stats2["counters"].get("health_check_total", {}).get("svc", 0) == 2)
    check("health_check_by_probe tcp", stats2["counters"].get("health_check_by_probe", {}).get("tcp", 0) == 1)
    check("health_check_by_probe http", stats2["counters"].get("health_check_by_probe", {}).get("http", 0) == 1)
    check("health_check_success_total is 1", stats2["counters"].get("health_check_success_total", {}).get("svc", 0) == 1)

    # record_lease_event
    tel.record_lease_event("created", "svc", "i1")
    tel.record_lease_event("renewed", "svc", "i1")
    stats3 = tel.get_stats()
    check("lease_event_total created", stats3["counters"].get("lease_event_total", {}).get("created", 0) == 1)
    check("lease_event_total renewed", stats3["counters"].get("lease_event_total", {}).get("renewed", 0) == 1)

    # record_recovery
    tel.record_recovery("svc", "i1", success=True)
    tel.record_recovery("svc", "i1", success=False)
    stats4 = tel.get_stats()
    check("recovery_total is 2", stats4["counters"].get("recovery_total", {}).get("svc", 0) == 2)
    check("recovery_success_total is 1", stats4["counters"].get("recovery_success_total", {}).get("svc", 0) == 1)
    check("recovery_failure_total is 1", stats4["counters"].get("recovery_failure_total", {}).get("svc", 0) == 1)

    # start_span / end_span
    span_id = tel.start_span("register", service_name="svc")
    check("start_span returns id", isinstance(span_id, str))
    check("span is open", span_id in tel._open_spans)
    check("open_span has operation", tel._open_spans[span_id]["operation"] == "register")
    check("open_span has service_name", tel._open_spans[span_id]["service_name"] == "svc")
    check("open_span status in_progress", tel._open_spans[span_id]["status"] == "in_progress")

    tel.end_span(span_id, status="ok")
    check("span no longer open", span_id not in tel._open_spans)
    check("span is completed", len(tel._spans) == 1)
    completed = tel._spans[0]
    check("completed span has end_time", completed["end_time"] is not None)
    check("completed span has duration_ms", completed["duration_ms"] is not None)
    check("completed span status is ok", completed["status"] == "ok")

    # end_span with unknown id
    tel.end_span("nonexistent_id")
    check("end_span unknown is no-op", len(tel._spans) == 1)

    # get_spans
    spans = tel.get_spans()
    check("get_spans returns list", isinstance(spans, list))
    check("get_spans has 1 entry", len(spans) == 1)
    spans_svc = tel.get_spans("svc")
    check("get_spans filtered by service", len(spans_svc) == 1)
    spans_other = tel.get_spans("other")
    check("get_spans other is empty", len(spans_other) == 0)

    # get_traces
    traces = tel.get_traces()
    check("get_traces returns list", isinstance(traces, list))
    check("get_traces has 1 trace", len(traces) == 1)
    check("trace has trace_id", "trace_id" in traces[0])
    check("trace has spans list", isinstance(traces[0]["spans"], list))

    # get_stats final
    final_stats = tel.get_stats()
    check("stats open_span_count is 0", final_stats["open_span_count"] == 0)
    check("stats completed_span_count is 1", final_stats["completed_span_count"] == 1)
    check("stats has counters", isinstance(final_stats["counters"], dict))
    check("stats has latencies", isinstance(final_stats["latencies"], dict))


# ── Section 16: Policies ──────────────────────────────────────────────


def test_policies():
    print("\n=== 16. Policies (AlwaysHealthy, Threshold, ConsecutiveFailure, Adaptive, PolicyFactory) ===")

    # AlwaysHealthyPolicy
    ah = AlwaysHealthyPolicy()
    check("AlwaysHealthy is_healthy True with empty", ah.is_healthy([]) is True)
    check("AlwaysHealthy is_healthy True with failures", ah.is_healthy([{"success": False}]) is True)
    check("AlwaysHealthy is_healthy True with success", ah.is_healthy([{"success": True}]) is True)
    check("AlwaysHealthy stats policy_type", ah.get_stats()["policy_type"] == "always_healthy")

    # ThresholdPolicy
    tp = ThresholdPolicy(threshold=0.5)
    check("threshold is 0.5", tp._threshold == 0.5)
    check("Threshold empty is healthy", tp.is_healthy([]) is True)
    check("Threshold 1/2 success at 0.5 is healthy", tp.is_healthy([{"success": True}, {"success": False}]) is True)
    check("Threshold 1/3 success at 0.5 is unhealthy", tp.is_healthy([{"success": True}, {"success": False}, {"success": False}]) is False)
    check("Threshold all success is healthy", tp.is_healthy([{"success": True}, {"success": True}]) is True)
    check("Threshold stats policy_type", tp.get_stats()["policy_type"] == "threshold")
    check("Threshold stats has threshold", tp.get_stats()["threshold"] == 0.5)
    check("Threshold stats eval_count > 0", tp.get_stats()["eval_count"] > 0)

    # ThresholdPolicy clamping
    tp_clamped = ThresholdPolicy(threshold=1.5)
    check("threshold clamped to 1.0", tp_clamped._threshold == 1.0)
    tp_clamped2 = ThresholdPolicy(threshold=-0.5)
    check("threshold clamped to 0.0", tp_clamped2._threshold == 0.0)

    # ConsecutiveFailurePolicy
    cf = ConsecutiveFailurePolicy(max_failures=3)
    check("max_failures is 3", cf._max_failures == 3)
    check("Consecutive empty is healthy", cf.is_healthy([]) is True)
    check("Consecutive 1 failure is healthy", cf.is_healthy([{"success": True}, {"success": False}]) is True)
    check("Consecutive 2 failures is healthy", cf.is_healthy([{"success": True}, {"success": False}, {"success": False}]) is True)
    check("Consecutive 3 failures is unhealthy", cf.is_healthy([{"success": False}, {"success": False}, {"success": False}]) is False)
    check("Consecutive with success in middle is healthy", cf.is_healthy([{"success": False}, {"success": True}, {"success": False}]) is True)
    check("Consecutive stats policy_type", cf.get_stats()["policy_type"] == "consecutive_failure")
    check("Consecutive stats has current_streak", "current_streak" in cf.get_stats())
    check("Consecutive stats eval_count > 0", cf.get_stats()["eval_count"] > 0)

    # ConsecutiveFailurePolicy max_failures clamping
    cf_clamped = ConsecutiveFailurePolicy(max_failures=0)
    check("max_failures clamped to 1", cf_clamped._max_failures == 1)

    # AdaptivePolicy
    ap = AdaptivePolicy(window_size=5, failure_ratio=0.3)
    check("window_size is 5", ap._window_size == 5)
    check("failure_ratio is 0.3", ap._failure_ratio == 0.3)
    check("Adaptive empty is healthy", ap.is_healthy([]) is True)
    check("Adaptive all success is healthy", ap.is_healthy([{"success": True}] * 5) is True)
    check("Adaptive all failure is unhealthy", ap.is_healthy([{"success": False}] * 5) is False)
    check("Adaptive 1/5 failure is healthy", ap.is_healthy([{"success": False}, {"success": True}, {"success": True}, {"success": True}, {"success": True}]) is True)
    check("Adaptive stats policy_type", ap.get_stats()["policy_type"] == "adaptive")
    check("Adaptive stats has window_size", ap.get_stats()["window_size"] == 5)
    check("Adaptive stats has current_window_size", "current_window_size" in ap.get_stats())
    check("Adaptive stats eval_count > 0", ap.get_stats()["eval_count"] > 0)

    # AdaptivePolicy clamping
    ap_clamped = AdaptivePolicy(window_size=-1, failure_ratio=1.5)
    check("window_size clamped to 1", ap_clamped._window_size == 1)
    check("failure_ratio clamped to 1.0", ap_clamped._failure_ratio == 1.0)

    # PolicyFactory
    check("PolicyFactory creates AlwaysHealthy", isinstance(PolicyFactory.create("always"), AlwaysHealthyPolicy))
    check("PolicyFactory creates AlwaysHealthy (alt)", isinstance(PolicyFactory.create("always_healthy"), AlwaysHealthyPolicy))
    check("PolicyFactory creates ThresholdPolicy", isinstance(PolicyFactory.create("threshold"), ThresholdPolicy))
    check("PolicyFactory creates ConsecutiveFailurePolicy", isinstance(PolicyFactory.create("consecutive"), ConsecutiveFailurePolicy))
    check("PolicyFactory creates AdaptivePolicy", isinstance(PolicyFactory.create("adaptive"), AdaptivePolicy))

    # PolicyFactory with kwargs
    tp_factory = PolicyFactory.create("threshold", threshold=0.8)
    check("PolicyFactory threshold kwargs", tp_factory._threshold == 0.8)
    cf_factory = PolicyFactory.create("consecutive", max_failures=5)
    check("PolicyFactory consecutive kwargs", cf_factory._max_failures == 5)
    ap_factory = PolicyFactory.create("adaptive", window_size=20, failure_ratio=0.5)
    check("PolicyFactory adaptive kwargs window", ap_factory._window_size == 20)
    check("PolicyFactory adaptive kwargs ratio", ap_factory._failure_ratio == 0.5)

    # PolicyFactory default
    default_policy = PolicyFactory.create()
    check("PolicyFactory default is ConsecutiveFailure", isinstance(default_policy, ConsecutiveFailurePolicy))

    # PolicyFactory unknown raises
    try:
        PolicyFactory.create("unknown_type")
        check("PolicyFactory unknown raises ValueError", False)
    except ValueError:
        check("PolicyFactory unknown raises ValueError", True)

    # HealthPolicy abstract
    check("HealthPolicy is abstract (has __abstractmethods__)", len(HealthPolicy.__abstractmethods__) > 0)


# ── Main ──────────────────────────────────────────────────────────────


async def main():
    print("ICYQuant Service Discovery Part 1.2 - Validation Tests")
    print("=" * 60)

    await test_heartbeat_service()
    await test_heartbeat_scheduler()
    await test_async_lease_manager()
    await test_probes()
    await test_health_checker()
    await test_health_monitor()
    await test_readiness_probe()
    await test_liveness_probe()
    await test_startup_probe()
    test_phi_accrual_detector()
    test_quarantine_manager()
    await test_lease_expiration()
    await test_service_recovery()
    await test_health_scheduler()
    test_telemetry()
    test_policies()

    print("\n" + "=" * 60)
    print(f"=== Summary ===")
    print(f"Passed: {checks_passed}")
    print(f"Failed: {checks_failed}")
    print(f"Total: {checks_passed + checks_failed}")
    if checks_failed > 0:
        print("RESULT: FAILED")
    else:
        print("RESULT: ALL PASSED")


if __name__ == "__main__":
    asyncio.run(main())
