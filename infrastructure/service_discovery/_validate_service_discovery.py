"""Comprehensive validation tests for the ICYQuant service discovery module.

This module exercises the public API of ``infrastructure.service_discovery``
covering models, rich classes, registry, resolver, selectors, adapters,
events, metrics, health, diagnostics, and the top-level manager.

Run with::

    python -m infrastructure.service_discovery._validate_service_discovery
"""

import asyncio
from infrastructure.service_discovery import *

checks_passed = 0
checks_failed = 0


def check(name, condition):
    global checks_passed, checks_failed
    if condition:
        checks_passed += 1
    else:
        checks_failed += 1
        print(f"  [FAIL] {name}")


def assert_eq(actual, expected, name):
    check(name, actual == expected)


# ---------------------------------------------------------------------------
# 1. ServiceEndpoint
# ---------------------------------------------------------------------------
def test_service_endpoint():
    print("\n=== 1. ServiceEndpoint ===")
    ep = ServiceEndpoint("localhost", 8080)
    check("endpoint host", ep.host == "localhost")
    check("endpoint port", ep.port == 8080)
    check("endpoint default protocol", ep.protocol == "http")
    check("endpoint default path", ep.path == "")
    check("endpoint default metadata empty", ep.metadata == {})

    check("to_url simple", ep.to_url() == "http://localhost:8080")

    ep_https = ServiceEndpoint("api.example.com", 443, "https", "/v1/users")
    check("to_url https path", ep_https.to_url() == "https://api.example.com:443/v1/users")

    ep_nopath = ServiceEndpoint("host", 9000, path="health")
    check("to_url normalizes path", ep_nopath.to_url() == "http://host:9000/health")

    d = ep_https.to_dict()
    check("to_dict host", d["host"] == "api.example.com")
    check("to_dict port", d["port"] == 443)
    check("to_dict protocol", d["protocol"] == "https")
    check("to_dict path", d["path"] == "/v1/users")

    ep_back = ServiceEndpoint.from_dict(d)
    check("from_dict host", ep_back.host == "api.example.com")
    check("from_dict port", ep_back.port == 443)
    check("from_dict roundtrip equality", ep_back == ep_https)

    ep_meta_a = ServiceEndpoint("h", 1, metadata={"k": "a"})
    ep_meta_b = ServiceEndpoint("h", 1, metadata={"k": "b"})
    check("equality ignores metadata", ep_meta_a == ep_meta_b)

    ep_empty = ServiceEndpoint.from_dict({})
    check("from_dict empty host", ep_empty.host == "")
    check("from_dict empty port", ep_empty.port == 0)

    check("str returns url", str(ep) == "http://localhost:8080")


# ---------------------------------------------------------------------------
# 2. ServiceInstance
# ---------------------------------------------------------------------------
def test_service_instance():
    print("\n=== 2. ServiceInstance ===")
    inst = ServiceInstance("order-service", "inst-1", "10.0.0.1", 8080)
    check("instance service_name", inst.service_name == "order-service")
    check("instance instance_id", inst.instance_id == "inst-1")
    check("instance host", inst.host == "10.0.0.1")
    check("instance port", inst.port == 8080)
    check("instance default version", inst.version == "1.0.0")
    check("instance default namespace", inst.namespace == "default")
    check("instance default status", inst.status == ServiceStatus.CREATED)
    check("instance default healthy flag", inst.healthy is True)
    check("is_healthy false for CREATED", inst.is_healthy() is False)

    inst.update_status(ServiceStatus.REGISTERED)
    check("is_healthy true after REGISTERED", inst.is_healthy() is True)

    inst.update_status(ServiceStatus.HEALTHY)
    check("status is HEALTHY", inst.status == ServiceStatus.HEALTHY)
    check("healthy flag true after HEALTHY", inst.healthy is True)

    inst.update_status(ServiceStatus.UNHEALTHY)
    check("status is UNHEALTHY", inst.status == ServiceStatus.UNHEALTHY)
    check("healthy flag false after UNHEALTHY", inst.healthy is False)
    check("is_healthy false after UNHEALTHY", inst.is_healthy() is False)

    inst_meta = ServiceInstance(
        "svc", "i2", "host", 9090, metadata={"protocol": "https", "path": "/api"}
    )
    endpoint = inst_meta.to_endpoint()
    check("to_endpoint host", endpoint.host == "host")
    check("to_endpoint port", endpoint.port == 9090)
    check("to_endpoint protocol from metadata", endpoint.protocol == "https")
    check("to_endpoint path from metadata", endpoint.path == "/api")

    d = inst.to_dict()
    check("to_dict service_name", d["service_name"] == "order-service")
    check("to_dict status value", d["status"] == "unhealthy")
    check("to_dict healthy", d["healthy"] is False)

    inst_back = ServiceInstance.from_dict(d)
    check("from_dict service_name", inst_back.service_name == "order-service")
    check("from_dict status", inst_back.status == ServiceStatus.UNHEALTHY)

    inst_a = ServiceInstance("svc", "i1", "h1", 1)
    inst_b = ServiceInstance("svc", "i1", "h2", 2)
    check("equality by name/id/namespace", inst_a == inst_b)


# ---------------------------------------------------------------------------
# 3. ServiceMetadata
# ---------------------------------------------------------------------------
def test_service_metadata():
    print("\n=== 3. ServiceMetadata ===")
    meta = ServiceMetadata(
        environment="production",
        region="us-east-1",
        zone="zone-a",
        weight=5,
        protocol="https",
        capabilities=["auth", "cache"],
        tags=["v1", "stable"],
        labels={"team": "core", "tier": "api"},
    )
    check("meta environment", meta.environment == "production")
    check("meta region", meta.region == "us-east-1")
    check("meta weight", meta.weight == 5)
    check("meta protocol", meta.protocol == "https")
    check("has_capability auth", meta.has_capability("auth") is True)
    check("has_capability missing", meta.has_capability("missing") is False)
    check("has_tag v1", meta.has_tag("v1") is True)
    check("has_tag missing", meta.has_tag("missing") is False)
    check("get_label team", meta.get_label("team") == "core")
    check("get_label default", meta.get_label("absent", "default") == "default")

    check("matches empty filter", meta.matches({}) is True)
    check("matches environment", meta.matches({"environment": "production"}) is True)
    check("matches environment mismatch", meta.matches({"environment": "staging"}) is False)
    check("matches region", meta.matches({"region": "us-east-1"}) is True)
    check("matches capability", meta.matches({"capability": "auth"}) is True)
    check("matches tag", meta.matches({"tag": "v1"}) is True)
    check("matches label", meta.matches({"label": {"team": "core"}}) is True)
    check("matches label mismatch", meta.matches({"label": {"team": "other"}}) is False)
    check("matches capabilities list", meta.matches({"capabilities": ["auth", "cache"]}) is True)
    check("matches capabilities subset", meta.matches({"capabilities": ["auth"]}) is True)
    check("matches capabilities missing", meta.matches({"capabilities": ["nope"]}) is False)
    check("matches tags list", meta.matches({"tags": ["v1", "stable"]}) is True)

    d = meta.to_dict()
    check("to_dict environment", d["environment"] == "production")
    check("to_dict capabilities", d["capabilities"] == ["auth", "cache"])
    check("to_dict labels", d["labels"] == {"team": "core", "tier": "api"})

    meta_back = ServiceMetadata.from_dict(d)
    check("from_dict equality", meta_back == meta)


# ---------------------------------------------------------------------------
# 4. Service
# ---------------------------------------------------------------------------
def test_service():
    print("\n=== 4. Service ===")
    svc = Service("order-service", "default")
    check("service name", svc.name == "order-service")
    check("service namespace", svc.namespace == "default")
    check("service empty instance count", svc.get_instance_count() == 0)

    i1 = ServiceInstance("order-service", "i1", "h1", 8080, status=ServiceStatus.REGISTERED)
    i2 = ServiceInstance("order-service", "i2", "h2", 8081, version="2.0.0", status=ServiceStatus.REGISTERED)
    i3 = ServiceInstance("order-service", "i3", "h3", 8082, status=ServiceStatus.CREATED)

    svc.add_instance(i1)
    svc.add_instance(i2)
    svc.add_instance(i3)
    check("instance count after adds", svc.get_instance_count() == 3)

    healthy = svc.get_instances(healthy_only=True)
    check("healthy only count", len(healthy) == 2)
    all_inst = svc.get_instances(healthy_only=False)
    check("all instances count", len(all_inst) == 3)

    versions = svc.get_versions()
    check("versions sorted", versions == ["1.0.0", "2.0.0"])

    got = svc.get_instance("i1")
    check("get_instance by id", got is not None and got.instance_id == "i1")
    check("get_instance missing", svc.get_instance("nope") is None)

    svc.remove_instance("i3")
    check("count after remove", svc.get_instance_count() == 2)
    check("removed not found", svc.get_instance("i3") is None)

    stats = svc.get_stats()
    check("stats name", stats["name"] == "order-service")
    check("stats total", stats["total_instances"] == 2)
    check("stats healthy", stats["healthy_instances"] == 2)
    check("stats unhealthy", stats["unhealthy_instances"] == 0)
    check("stats by_status has registered", "registered" in stats["by_status"])

    d = svc.to_dict()
    check("to_dict name", d["name"] == "order-service")
    check("to_dict instance_count", d["instance_count"] == 2)


# ---------------------------------------------------------------------------
# 5. Namespace + NamespaceManager
# ---------------------------------------------------------------------------
def test_namespace():
    print("\n=== 5. Namespace + NamespaceManager ===")
    check("default namespaces count", len(DEFAULT_NAMESPACES) == 7)
    check("production in defaults", "production" in DEFAULT_NAMESPACES)
    check("live-trading in defaults", "live-trading" in DEFAULT_NAMESPACES)

    ns = Namespace("custom", "A custom namespace")
    check("namespace name", ns.name == "custom")
    check("namespace description", ns.description == "A custom namespace")
    ns.add_service("svc-a")
    ns.add_service("svc-b")
    check("namespace has_service", ns.has_service("svc-a") is True)
    check("namespace has_service missing", ns.has_service("nope") is False)
    check("namespace get_services sorted", ns.get_services() == ["svc-a", "svc-b"])

    ns_dict = ns.to_dict()
    check("namespace to_dict name", ns_dict["name"] == "custom")
    check("namespace to_dict service_count", ns_dict["service_count"] == 2)

    mgr = NamespaceManager()
    check("manager default count", len(mgr.list_namespaces()) == 7)
    check("manager get production", mgr.get_namespace("production") is not None)
    check("manager get missing", mgr.get_namespace("nope") is None)

    new_ns = mgr.create_namespace("custom-ns", "test")
    check("create namespace", new_ns.name == "custom-ns")
    check("list count after create", len(mgr.list_namespaces()) == 8)

    try:
        mgr.create_namespace("custom-ns")
        check("duplicate create raises", False)
    except NamespaceError:
        check("duplicate create raises", True)

    mgr.add_service_to_namespace("custom-ns", "my-service")
    services = mgr.get_services_in_namespace("custom-ns")
    check("services in namespace", services == ["my-service"])

    try:
        mgr.delete_namespace("production")
        check("delete default raises", False)
    except NamespaceError:
        check("delete default raises", True)

    mgr.delete_namespace("custom-ns")
    check("list count after delete", len(mgr.list_namespaces()) == 7)
    check("deleted not found", mgr.get_namespace("custom-ns") is None)

    stats = mgr.get_stats()
    check("stats total_namespaces", stats["total_namespaces"] == 7)
    check("stats default_namespaces list", len(stats["default_namespaces"]) == 7)


# ---------------------------------------------------------------------------
# 6. ServiceValidator
# ---------------------------------------------------------------------------
def test_service_validator():
    print("\n=== 6. ServiceValidator ===")
    v = ServiceValidator()
    check("valid service_name", v.validate_service_name("order-service") is True)
    check("valid service_name underscore", v.validate_service_name("my_service") is True)
    check("invalid service_name empty", v.validate_service_name("") is False)
    check("invalid service_name digit start", v.validate_service_name("1service") is False)
    check("invalid service_name none", v.validate_service_name(None) is False)

    check("valid port", v.validate_port(8080) is True)
    check("valid port boundary 1", v.validate_port(1) is True)
    check("valid port boundary 65535", v.validate_port(65535) is True)
    check("invalid port 0", v.validate_port(0) is False)
    check("invalid port too big", v.validate_port(70000) is False)
    check("invalid port negative", v.validate_port(-1) is False)

    check("valid version", v.validate_version("1.0.0") is True)
    check("valid version prerelease", v.validate_version("1.2.3-alpha") is True)
    check("invalid version empty", v.validate_version("") is False)
    check("invalid version text", v.validate_version("latest") is False)

    check("valid namespace", v.validate_namespace("production") is True)
    check("invalid namespace empty", v.validate_namespace("") is False)

    check("valid host", v.validate_host("localhost") is True)
    check("invalid host empty", v.validate_host("") is False)
    check("invalid host dot prefix", v.validate_host(".bad") is False)

    good = ServiceInstance("valid-svc", "inst-1", "localhost", 8080, version="1.0.0")
    errors = v.validate_instance(good)
    check("valid instance no errors", errors == [])

    bad = ServiceInstance("", "", "", 0, version="bad")
    errors_bad = v.validate_instance(bad)
    check("invalid instance has errors", len(errors_bad) > 0)

    stats = v.get_stats()
    check("validator stats total", stats["total_validations"] >= 2)
    check("validator stats failures", stats["total_failures"] >= 1)


# ---------------------------------------------------------------------------
# 7. ServiceRepository
# ---------------------------------------------------------------------------
def test_service_repository():
    print("\n=== 7. ServiceRepository ===")
    repo = ServiceRepository(ttl=30.0)
    check("repo default ttl", repo.get_stats()["ttl_seconds"] == 30.0)

    check("get_service miss", repo.get_service("nope") is None)
    inst = ServiceInstance("cache-svc", "i1", "h", 8080, status=ServiceStatus.REGISTERED)
    svc = Service("cache-svc", "default")
    svc.add_instance(inst)
    repo.set_service(svc)

    got = repo.get_service("cache-svc")
    check("get_service hit", got is not None)
    check("get_service name", got.name == "cache-svc")

    instances = repo.get_instances("cache-svc")
    check("get_instances count", len(instances) == 1)
    check("get_instances miss empty", repo.get_instances("missing") == [])

    all_svc = repo.get_all_services("default")
    check("get_all_services count", len(all_svc) == 1)

    repo.invalidate("cache-svc")
    check("invalidate removes entry", repo.get_service("cache-svc") is None)

    repo.set_service(svc)
    repo.invalidate_all()
    check("invalidate_all clears", repo.get_service("cache-svc") is None)

    stats = repo.get_stats()
    check("stats has hits field", "hits" in stats)
    check("stats has misses field", "misses" in stats)
    check("stats current_entries zero", stats["current_entries"] == 0)


# ---------------------------------------------------------------------------
# 8. ServiceLifecycle
# ---------------------------------------------------------------------------
def test_service_lifecycle():
    print("\n=== 8. ServiceLifecycle ===")
    lc = ServiceLifecycle()
    check("default status CREATED", lc.get_status("svc", "i1") == ServiceStatus.CREATED)
    check("not terminal initially", lc.is_terminal("svc", "i1") is False)

    r1 = lc.transition("svc", "i1", ServiceStatus.REGISTERED)
    check("transition to REGISTERED success", r1["success"] is True)
    check("status after REGISTERED", lc.get_status("svc", "i1") == ServiceStatus.REGISTERED)

    lc.transition("svc", "i1", ServiceStatus.HEALTHY)
    check("status after HEALTHY", lc.get_status("svc", "i1") == ServiceStatus.HEALTHY)

    lc.transition("svc", "i1", ServiceStatus.UNHEALTHY)
    check("status after UNHEALTHY", lc.get_status("svc", "i1") == ServiceStatus.UNHEALTHY)

    lc.transition("svc", "i1", ServiceStatus.DEREGISTERED)
    lc.transition("svc", "i1", ServiceStatus.REMOVED)
    check("status after REMOVED", lc.get_status("svc", "i1") == ServiceStatus.REMOVED)
    check("is_terminal true after REMOVED", lc.is_terminal("svc", "i1") is True)

    history = lc.get_history("svc")
    check("history has entries", len(history) == 5)
    history_i1 = lc.get_history("svc", "i1")
    check("history filtered by instance", len(history_i1) == 5)

    invalid = ServiceLifecycle()
    try:
        invalid.transition("bad", "i1", ServiceStatus.HEALTHY)
        check("invalid transition raises", False)
    except ServiceDiscoveryError:
        check("invalid transition raises", True)

    stats = lc.get_stats()
    check("stats tracked_instances", stats["tracked_instances"] == 1)
    check("stats total_transitions", stats["total_transitions"] == 5)
    check("stats terminal_instances", stats["terminal_instances"] == 1)


# ---------------------------------------------------------------------------
# 9. ServiceLease + LeaseManager
# ---------------------------------------------------------------------------
def test_service_lease():
    print("\n=== 9. ServiceLease + LeaseManager ===")
    lease = ServiceLease("svc", "i1", ttl=30)
    check("lease service_name", lease.service_name == "svc")
    check("lease ttl", lease.ttl == 30)
    check("lease not expired", lease.is_expired() is False)
    check("lease remaining > 0", lease.get_remaining_ttl() > 0)

    lease.renew()
    check("lease not expired after renew", lease.is_expired() is False)

    lease.expire()
    check("lease expired after expire", lease.is_expired() is True)
    check("lease remaining 0 after expire", lease.get_remaining_ttl() == 0)

    try:
        lease.renew()
        check("renew after expire raises", False)
    except LeaseExpiredError:
        check("renew after expire raises", True)

    mgr = LeaseManager()
    l1 = mgr.create_lease("svc-a", "i1", ttl=60)
    check("create_lease returns lease", l1 is not None)
    check("get_lease returns lease", mgr.get_lease("svc-a", "i1") is not None)
    check("get_lease missing", mgr.get_lease("svc-a", "nope") is None)

    renewed = mgr.renew_lease("svc-a", "i1")
    check("renew_lease returns lease", renewed is not None)
    check("renew_lease missing returns None", mgr.renew_lease("svc-a", "nope") is None)

    l2 = mgr.create_lease("svc-b", "i2", ttl=30)
    l2.expire()
    expired_list = mgr.get_expired_leases()
    check("get_expired_leases count", len(expired_list) == 1)

    cleaned = mgr.cleanup_expired()
    check("cleanup_expired count", cleaned == 1)
    check("lease removed after cleanup", mgr.get_lease("svc-b", "i2") is None)

    mgr.expire_lease("svc-a", "i1")
    check("expire_lease removes", mgr.get_lease("svc-a", "i1") is None)

    stats = mgr.get_stats()
    check("stats total_leases", stats["total_leases"] == 0)
    check("stats created_total", stats["created_total"] >= 2)
    check("stats expired_total", stats["expired_total"] >= 2)


# ---------------------------------------------------------------------------
# 10. MemoryAdapter (async)
# ---------------------------------------------------------------------------
async def test_memory_adapter():
    print("\n=== 10. MemoryAdapter ===")
    adapter = MemoryAdapter()
    check("memory connected initially", adapter.is_connected() is True)
    await adapter.connect()
    check("memory connected after connect", adapter.is_connected() is True)

    inst = ServiceInstance("data-svc", "m1", "10.0.0.1", 7070)
    await adapter.register(inst)
    check("register sets REGISTERED", inst.status == ServiceStatus.REGISTERED)

    discovered = await adapter.discover("data-svc")
    check("discover returns instance", len(discovered) == 1)
    check("discover instance id", discovered[0].instance_id == "m1")

    discovered_missing = await adapter.discover("nope")
    check("discover missing empty", discovered_missing == [])

    await adapter.heartbeat("data-svc", "m1")
    check("heartbeat no error", True)

    await adapter.update_instance("data-svc", "m1", {"weight": 10})
    svc = await adapter.get_service("data-svc")
    updated_inst = svc.get_instance("m1")
    check("update_instance weight", updated_inst.weight == 10)

    services = await adapter.list_services()
    check("list_services count", len(services) == 1)
    check("list_services name", services[0].name == "data-svc")

    await adapter.deregister("data-svc", "m1")
    after_dereg = await adapter.discover("data-svc")
    check("discover empty after deregister", after_dereg == [])

    stats = adapter.get_stats()
    check("stats adapter_type", stats["adapter_type"] == "memory")
    check("stats register_count", stats["register_count"] == 1)
    check("stats deregister_count", stats["deregister_count"] == 1)

    await adapter.disconnect()
    check("memory disconnected", adapter.is_connected() is False)


# ---------------------------------------------------------------------------
# 11. EtcdAdapter, ConsulAdapter, KubernetesAdapter (async)
# ---------------------------------------------------------------------------
async def test_stub_adapters():
    print("\n=== 11. EtcdAdapter, ConsulAdapter, KubernetesAdapter ===")
    etcd = EtcdAdapter()
    check("etcd not connected initially", etcd.is_connected() is False)
    check("etcd stats type", etcd.get_stats()["adapter_type"] == "etcd")
    check("etcd endpoints default", len(etcd.endpoints) == 1)
    await etcd.disconnect()
    check("etcd disconnected", etcd.is_connected() is False)

    consul = ConsulAdapter()
    check("consul not connected initially", consul.is_connected() is False)
    check("consul stats type", consul.get_stats()["adapter_type"] == "consul")
    check("consul host default", consul.host == "localhost")
    check("consul port default", consul.port == 8500)
    await consul.disconnect()
    check("consul disconnected", consul.is_connected() is False)

    k8s = KubernetesAdapter()
    check("k8s not connected initially", k8s.is_connected() is False)
    check("k8s stats type", k8s.get_stats()["adapter_type"] == "kubernetes")
    check("k8s namespace default", k8s.namespace == "default")
    await k8s.disconnect()
    check("k8s disconnected", k8s.is_connected() is False)


# ---------------------------------------------------------------------------
# 12. AdapterFactory
# ---------------------------------------------------------------------------
def test_adapter_factory():
    print("\n=== 12. AdapterFactory ===")
    mem = AdapterFactory.create("memory")
    check("factory memory type", isinstance(mem, MemoryAdapter))

    etcd = AdapterFactory.create("etcd")
    check("factory etcd type", isinstance(etcd, EtcdAdapter))

    consul = AdapterFactory.create("consul")
    check("factory consul type", isinstance(consul, ConsulAdapter))

    k8s = AdapterFactory.create("kubernetes")
    check("factory kubernetes type", isinstance(k8s, KubernetesAdapter))

    upper = AdapterFactory.create("MEMORY")
    check("factory case insensitive", isinstance(upper, MemoryAdapter))

    supported = AdapterFactory.supported_adapters()
    check("supported has memory", "memory" in supported)
    check("supported has etcd", "etcd" in supported)
    check("supported has consul", "consul" in supported)
    check("supported has kubernetes", "kubernetes" in supported)
    check("supported count", len(supported) == 4)

    try:
        AdapterFactory.create("unknown")
        check("unknown adapter raises", False)
    except ValueError:
        check("unknown adapter raises", True)


# ---------------------------------------------------------------------------
# 13. ServiceRegistry (async)
# ---------------------------------------------------------------------------
async def test_service_registry():
    print("\n=== 13. ServiceRegistry ===")
    registry = ServiceRegistry()
    registry.namespace_manager.create_namespace("default")
    check("registry adapter type", registry.get_stats()["adapter_type"] == "InMemoryRegistryAdapter")

    inst = ServiceInstance("trade-svc", "r1", "host1", 8001, version="1.0.0")
    result = await registry.register(inst)
    check("register success", result["registered"] is True)
    check("register instance_count", result["instance_count"] == 1)

    discovered = await registry.discover("trade-svc")
    check("discover count", len(discovered) == 1)
    check("discover instance", discovered[0].instance_id == "r1")

    svc = await registry.get_service("trade-svc")
    check("get_service found", svc is not None)
    check("get_service name", svc.name == "trade-svc")

    services = await registry.list_services()
    check("list_services count", len(services) == 1)

    upd = await registry.update_instance("trade-svc", "r1", {"weight": 7})
    check("update success", upd["updated"] is True)
    check("update applied weight", "weight" in upd["applied_fields"])
    discovered_after = await registry.discover("trade-svc")
    check("update weight value", discovered_after[0].weight == 7)

    dereg = await registry.deregister("trade-svc", "r1")
    check("deregister success", dereg["deregistered"] is True)
    after_dereg = await registry.discover("trade-svc")
    check("discover empty after dereg", after_dereg == [])

    stats = registry.get_stats()
    check("stats register_count", stats["register_count"] == 1)
    check("stats deregister_count", stats["deregister_count"] == 1)


# ---------------------------------------------------------------------------
# 14. ServiceResolver (async)
# ---------------------------------------------------------------------------
async def test_service_resolver():
    print("\n=== 14. ServiceResolver ===")
    registry = ServiceRegistry()
    registry.namespace_manager.create_namespace("default")
    resolver = ServiceResolver(registry)

    inst1 = ServiceInstance("resolve-svc", "s1", "h1", 8001, status=ServiceStatus.REGISTERED)
    inst2 = ServiceInstance("resolve-svc", "s2", "h2", 8002, status=ServiceStatus.REGISTERED)
    await registry.register(inst1)
    await registry.register(inst2)

    resolved = await resolver.resolve("resolve-svc")
    check("resolve returns instance", resolved is not None)
    check("resolve service_name", resolved.service_name == "resolve-svc")

    all_instances = await resolver.resolve_all("resolve-svc")
    check("resolve_all count", len(all_instances) == 2)

    endpoint = await resolver.resolve_endpoint("resolve-svc")
    check("resolve_endpoint returns endpoint", endpoint is not None)
    check("resolve_endpoint port", endpoint.port in (8001, 8002))

    missing = await resolver.resolve("nope-svc")
    check("resolve missing returns None", missing is None)

    missing_ep = await resolver.resolve_endpoint("nope-svc")
    check("resolve_endpoint missing returns None", missing_ep is None)

    stats = resolver.get_stats()
    check("stats resolve_count", stats["resolve_count"] >= 1)
    check("stats resolve_all_count", stats["resolve_all_count"] >= 1)
    check("stats selector", stats["selector"] == "RoundRobinSelector")


# ---------------------------------------------------------------------------
# 15. Selectors
# ---------------------------------------------------------------------------
def test_selectors():
    print("\n=== 15. Selectors ===")
    rr = RoundRobinSelector()
    instances = [
        ServiceInstance("svc", f"i{n}", "h", 8000 + n, status=ServiceStatus.REGISTERED)
        for n in range(3)
    ]
    first = rr.select(instances)
    check("round_robin first", first.instance_id == "i0")
    second = rr.select(instances)
    check("round_robin second", second.instance_id == "i1")
    third = rr.select(instances)
    check("round_robin third", third.instance_id == "i2")
    fourth = rr.select(instances)
    check("round_robin wraps", fourth.instance_id == "i0")
    check("round_robin empty", rr.select([]) is None)

    rnd = RandomSelector()
    pick = rnd.select(instances)
    check("random returns instance", pick is not None)
    check("random empty", rnd.select([]) is None)

    weighted = WeightedSelector()
    w_instances = [
        ServiceInstance("svc", "w1", "h", 1, weight=10, status=ServiceStatus.REGISTERED),
        ServiceInstance("svc", "w2", "h", 2, weight=1, status=ServiceStatus.REGISTERED),
    ]
    wpick = weighted.select(w_instances)
    check("weighted returns instance", wpick is not None)
    check("weighted empty", weighted.select([]) is None)

    zero_w = [ServiceInstance("svc", "z1", "h", 1, weight=0, status=ServiceStatus.REGISTERED)]
    check("weighted zero weight fallback", weighted.select(zero_w) is not None)

    factory_rr = SelectorFactory.create("round_robin")
    check("factory round_robin type", isinstance(factory_rr, RoundRobinSelector))
    factory_rand = SelectorFactory.create("random")
    check("factory random type", isinstance(factory_rand, RandomSelector))
    factory_w = SelectorFactory.create("weighted")
    check("factory weighted type", isinstance(factory_w, WeightedSelector))
    check("factory default", isinstance(SelectorFactory.create(), RoundRobinSelector))

    strategies = SelectorFactory.available_strategies()
    check("strategies has round_robin", "round_robin" in strategies)
    check("strategies count", len(strategies) == 3)

    try:
        SelectorFactory.create("bad")
        check("factory unknown raises", False)
    except ValueError:
        check("factory unknown raises", True)


# ---------------------------------------------------------------------------
# 16. ServiceEventBus (async)
# ---------------------------------------------------------------------------
async def test_service_event_bus():
    print("\n=== 16. ServiceEventBus ===")
    bus = ServiceEventBus(max_history=100)
    received = []

    def handler(event):
        received.append(event)

    bus.subscribe(ServiceEventType.SERVICE_REGISTERED, handler)
    event = ServiceEvent(
        ServiceEventType.SERVICE_REGISTERED,
        service_name="event-svc",
        instance_id="e1",
    )
    await bus.publish(event)
    check("subscriber received event", len(received) == 1)
    check("received event type", received[0].event_type == ServiceEventType.SERVICE_REGISTERED)
    check("received service_name", received[0].service_name == "event-svc")

    global_received = []
    bus.subscribe_all(lambda e: global_received.append(e))
    await bus.publish(event)
    check("global subscriber received", len(global_received) == 1)

    history = bus.get_history(service_name="event-svc")
    check("history filtered count", len(history) == 2)
    history_all = bus.get_history()
    check("history all count", len(history_all) == 2)

    stats = bus.get_stats()
    check("stats total_events", stats["total_events"] == 2)
    check("stats subscriber_count", stats["subscriber_count"] == 2)
    check("stats history_size", stats["history_size"] == 2)

    bus.unsubscribe(ServiceEventType.SERVICE_REGISTERED, handler)
    await bus.publish(event)
    check("no more specific after unsubscribe", len(received) == 2)

    bus.clear()
    check("clear empties history", bus.get_stats()["history_size"] == 0)

    ev_dict = event.to_dict()
    check("event to_dict type", ev_dict["event_type"] == "service.registered")
    check("event to_dict service_name", ev_dict["service_name"] == "event-svc")
    ev_back = ServiceEvent.from_dict(ev_dict)
    check("event from_dict type", ev_back.event_type == ServiceEventType.SERVICE_REGISTERED)


# ---------------------------------------------------------------------------
# 17. ServiceDiscoveryMetrics
# ---------------------------------------------------------------------------
def test_service_discovery_metrics():
    print("\n=== 17. ServiceDiscoveryMetrics ===")
    metrics = ServiceDiscoveryMetrics()
    metrics.record_registration("svc-a", success=True, duration=0.05)
    metrics.record_registration("svc-b", success=False, duration=0.02)
    metrics.record_discovery("svc-a", duration=0.01, result_count=3)

    total_reg = metrics.get_counter("icyquant_service_registered_total")
    check("counter registered total", total_reg == 2)

    success_reg = metrics.get_counter("icyquant_service_registered_success_total")
    check("counter success", success_reg == 1)

    failure_reg = metrics.get_counter("icyquant_service_registered_failure_total")
    check("counter failure", failure_reg == 1)

    discovery_count = metrics.get_counter("icyquant_service_discovery_total")
    check("counter discovery", discovery_count == 1)

    snap = metrics.snapshot()
    check("snapshot has counters", "counters" in snap)
    check("snapshot has gauges", "gauges" in snap)
    check("snapshot has histograms", "histograms" in snap)

    hist = metrics.get_histogram("icyquant_service_registry_latency_seconds")
    check("histogram count", hist["count"] == 3)
    check("histogram min >= 0", hist["min"] >= 0.0)

    metrics.reset()
    check("counter zero after reset", metrics.get_counter("icyquant_service_registered_total") == 0)

    stats = metrics.get_stats()
    check("stats counter_count", stats["counter_count"] == 0)
    check("stats gauge_count", stats["gauge_count"] == 0)


# ---------------------------------------------------------------------------
# 18. ServiceDiscoveryHealth (async)
# ---------------------------------------------------------------------------
async def test_service_discovery_health():
    print("\n=== 18. ServiceDiscoveryHealth ===")
    registry = ServiceRegistry()
    health = ServiceDiscoveryHealth(registry=registry)

    check("is_healthy false before check", health.is_healthy() is False)

    result = await health.check()
    check("check returns dict", isinstance(result, dict))
    check("check healthy overall", result["healthy"] is True)
    check("check has registry key", "registry" in result)
    check("check has summary", "summary" in result)
    check("check summary total", result["summary"]["total"] == 4)

    check("is_healthy true after check", health.is_healthy() is True)

    reg_check = health.check_registry()
    check("check_registry returns dict", isinstance(reg_check, dict))
    check("check_registry name", reg_check["name"] == "registry")
    check("check_registry healthy", reg_check["healthy"] is True)

    rep_check = health.check_repository()
    check("check_repository healthy", rep_check["healthy"] is True)

    stats = health.get_stats()
    check("stats total_checks", stats["total_checks"] == 4)
    check("stats registry_available", stats["registry_available"] is True)
    check("stats healthy_checks", stats["healthy_checks"] == 4)

    empty_health = ServiceDiscoveryHealth()
    empty_result = await empty_health.check()
    check("empty health all skipping", empty_result["healthy"] is True)


# ---------------------------------------------------------------------------
# 19. ServiceDiscoveryDiagnostics
# ---------------------------------------------------------------------------
def test_service_discovery_diagnostics():
    print("\n=== 19. ServiceDiscoveryDiagnostics ===")
    diag = ServiceDiscoveryDiagnostics(max_history=500)

    diag.record_operation("register", "diag-svc", "success", {"duration": 0.05})
    diag.record_operation("discover", "diag-svc", "success", {"duration": 0.01})
    diag.record_error("diag-svc", "connection failed", operation="connect")

    all_diag = diag.get_diagnostics()
    check("get_diagnostics count", len(all_diag) == 3)
    check("get_diagnostics most recent first", all_diag[0]["category"] == "error")

    svc_diag = diag.get_diagnostics("diag-svc")
    check("filtered by service count", len(svc_diag) == 3)

    other_diag = diag.get_diagnostics("other-svc")
    check("other service empty", other_diag == [])

    errors = diag.get_error_history("diag-svc")
    check("error history count", len(errors) == 1)
    check("error history message", errors[0]["error"] == "connection failed")

    ops = diag.get_operation_log("diag-svc")
    check("operation log count", len(ops) == 2)

    perf = diag.get_performance_report()
    check("perf report has services", "diag-svc" in perf["services"])
    check("perf report total_operations", perf["services"]["diag-svc"]["total_operations"] == 2)

    stats = diag.get_stats()
    check("stats total_entries", stats["total_entries"] == 3)
    check("stats tracked_services", stats["tracked_services"] == 1)
    check("stats by_category error", stats["by_category"].get("error") == 1)
    check("stats by_category operation", stats["by_category"].get("operation") == 2)

    diag.clear("diag-svc")
    check("clear removes service entries", len(diag.get_diagnostics("diag-svc")) == 0)
    check("stats empty after clear", diag.get_stats()["total_entries"] == 0)


# ---------------------------------------------------------------------------
# 20. ServiceDiscoveryManager (async)
# ---------------------------------------------------------------------------
async def test_service_discovery_manager():
    print("\n=== 20. ServiceDiscoveryManager ===")
    manager = ServiceDiscoveryManager()
    manager.get_namespace_manager().create_namespace("default")
    check("manager not running initially", manager.is_running() is False)
    check("get_registry not None", manager.get_registry() is not None)
    check("get_resolver not None", manager.get_resolver() is not None)
    check("get_namespace_manager not None", manager.get_namespace_manager() is not None)
    check("get_repository not None", manager.get_repository() is not None)

    await manager.startup()
    check("manager running after startup", manager.is_running() is True)

    inst = ServiceInstance("mgr-svc", "m1", "h", 8080)
    await manager.get_registry().register(inst)
    discovered = await manager.get_registry().discover("mgr-svc")
    check("register then discover", len(discovered) == 1)

    sync_result = await manager.synchronize()
    check("synchronize returns dict", isinstance(sync_result, dict))
    check("synchronize has synced key", "synced" in sync_result)
    check("synchronize has errors key", "errors" in sync_result)

    stats = manager.get_stats()
    check("stats running true", stats["running"] is True)
    check("stats adapter_type", stats["adapter_type"] == "InMemoryRegistryAdapter")
    check("stats has registry_stats", "registry_stats" in stats)
    check("stats has resolver_stats", "resolver_stats" in stats)
    check("stats has namespace_stats", "namespace_stats" in stats)
    check("stats sync_count", stats["sync_count"] == 1)

    await manager.shutdown()
    check("manager not running after shutdown", manager.is_running() is False)

    final_stats = manager.get_stats()
    check("final stats running false", final_stats["running"] is False)

    double_shutdown = ServiceDiscoveryManager()
    await double_shutdown.startup()
    await double_shutdown.shutdown()
    await double_shutdown.shutdown()
    check("double shutdown no error", double_shutdown.is_running() is False)


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("ICYQuant Service Discovery - Comprehensive Validation Tests")
    print("=" * 70)

    # Synchronous sections
    test_service_endpoint()
    test_service_instance()
    test_service_metadata()
    test_service()
    test_namespace()
    test_service_validator()
    test_service_repository()
    test_service_lifecycle()
    test_service_lease()
    test_adapter_factory()
    test_selectors()
    test_service_discovery_metrics()
    test_service_discovery_diagnostics()

    # Asynchronous sections
    asyncio.run(test_memory_adapter())
    asyncio.run(test_stub_adapters())
    asyncio.run(test_service_registry())
    asyncio.run(test_service_resolver())
    asyncio.run(test_service_event_bus())
    asyncio.run(test_service_discovery_health())
    asyncio.run(test_service_discovery_manager())

    print("\n" + "=" * 70)
    print(f"Total checks: {checks_passed + checks_failed}")
    print(f"Passed: {checks_passed}")
    print(f"Failed: {checks_failed}")
    print("=" * 70)
    if checks_failed == 0:
        print("ALL TESTS PASSED")
    else:
        print(f"{checks_failed} TEST(S) FAILED")
    return 0 if checks_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
