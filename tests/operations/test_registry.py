"""
Tests for ServiceRegistry (Commit 27 Part 1.1, spec sections 10-11, 21).

Registry 只回答"系统里有哪些服务"，不负责 Health / Metrics / Alert / Recovery。
"""

from __future__ import annotations

from services.operations import (
    RegisteredService,
    ServiceIdentity,
    ServiceRegistry,
)


def _service(
    service_id: str,
    name: str,
    metadata: dict | None = None,
) -> RegisteredService:
    return RegisteredService(
        identity=ServiceIdentity(
            service_id=service_id,
            name=name,
            version="0.4.0-alpha2",
            environment="production",
            instance_id=f"{service_id}-01",
        ),
        metadata=metadata or {},
    )


def test_registry_register():
    """spec section 21: register 后 contains 返回 True。"""
    registry = ServiceRegistry()

    service = _service("risk-engine", "Risk Engine")
    registry.register(service)

    assert registry.contains("risk-engine")


def test_registry_get_returns_registered_service():
    registry = ServiceRegistry()

    service = _service(
        "risk-engine",
        "Risk Engine",
        metadata={"region": "cn-east"},
    )
    registry.register(service)

    assert registry.get("risk-engine") is service
    assert registry.get("risk-engine").metadata == {
        "region": "cn-east",
    }


def test_registry_get_unknown_returns_none():
    registry = ServiceRegistry()

    assert registry.get("missing") is None


def test_registry_all_returns_registered_services():
    registry = ServiceRegistry()
    registry.register(_service("event-bus", "Event Bus"))
    registry.register(_service("ledger", "Ledger"))

    services = registry.all()

    assert {s.identity.service_id for s in services} == {
        "event-bus",
        "ledger",
    }


def test_registry_contains_unknown_is_false():
    registry = ServiceRegistry()
    registry.register(_service("event-bus", "Event Bus"))

    assert not registry.contains("ledger")


def test_registry_register_overwrites_same_id():
    registry = ServiceRegistry()

    registry.register(_service("risk-engine", "Risk Engine v1"))
    registry.register(_service("risk-engine", "Risk Engine v2"))

    assert len(registry.all()) == 1
    assert registry.get("risk-engine").identity.name == (
        "Risk Engine v2"
    )


def test_registry_supports_instance_ids():
    """同一 service 的多个实例以 service_id 唯一标识注册。"""
    registry = ServiceRegistry()

    registry.register(_service("risk-engine", "Risk Engine"))
    registry.register(_service("execution", "Execution"))

    assert registry.contains("risk-engine")
    assert registry.contains("execution")
    assert registry.get("risk-engine").identity.instance_id == (
        "risk-engine-01"
    )
