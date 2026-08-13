"""
Tests for ServiceDependency model and dependency validation
(Commit 27 Part 1.1, spec sections 8-9, 19-20).
"""

from services.operations import (
    RegisteredService,
    ServiceDependency,
    ServiceIdentity,
    ServiceRegistry,
    validate_dependency,
)


def _service(service_id: str, name: str) -> RegisteredService:
    return RegisteredService(
        identity=ServiceIdentity(
            service_id=service_id,
            name=name,
            version="0.4.0-alpha2",
            environment="production",
            instance_id=f"{service_id}-01",
        ),
        metadata={},
    )


def _registry_with(*service_ids: str) -> ServiceRegistry:
    registry = ServiceRegistry()
    for service_id in service_ids:
        registry.register(_service(service_id, service_id))
    return registry


def test_dependency_defaults():
    dependency = ServiceDependency(
        source_service="strategy-runtime",
        target_service="risk-engine",
    )

    assert dependency.source_service == "strategy-runtime"
    assert dependency.target_service == "risk-engine"
    assert dependency.required
    assert dependency.description == ""


def test_dependency_optional():
    dependency = ServiceDependency(
        source_service="analytics",
        target_service="market-data",
        required=False,
        description="best-effort data feed",
    )

    assert not dependency.required
    assert dependency.description == "best-effort data feed"


def test_validate_dependency_both_registered():
    """spec section 19：依赖两端的服务都必须存在。"""
    registry = _registry_with(
        "strategy-runtime",
        "risk-engine",
    )

    dependency = ServiceDependency(
        source_service="strategy-runtime",
        target_service="risk-engine",
    )

    assert validate_dependency(dependency, registry)


def test_validate_dependency_missing_source():
    registry = _registry_with("risk-engine")

    dependency = ServiceDependency(
        source_service="strategy-runtime",
        target_service="risk-engine",
    )

    assert not validate_dependency(dependency, registry)


def test_validate_dependency_missing_target():
    registry = _registry_with("strategy-runtime")

    dependency = ServiceDependency(
        source_service="strategy-runtime",
        target_service="risk-engine",
    )

    assert not validate_dependency(dependency, registry)


def test_validate_dependency_missing_both():
    registry = _registry_with("event-bus")

    dependency = ServiceDependency(
        source_service="strategy-runtime",
        target_service="risk-engine",
    )

    assert not validate_dependency(dependency, registry)


def test_validate_event_bus_downstream_chain():
    """spec section 20：Event Bus 是所有下游服务的 Root Dependency。"""
    registry = _registry_with(
        "event-bus",
        "ledger",
        "position",
        "oms",
        "risk",
    )

    for downstream in ("ledger", "position", "oms", "risk"):
        dependency = ServiceDependency(
            source_service=downstream,
            target_service="event-bus",
            required=True,
            description="consumes event stream",
        )
        assert validate_dependency(dependency, registry)
