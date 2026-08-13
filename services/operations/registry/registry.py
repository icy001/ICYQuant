"""
Service registry (Commit 27 Part 1.1, spec sections 10-11, 19).

Registry 只回答：系统里有哪些服务？

    event-bus / ledger / position / oms / risk / strategy-runtime /
    order-admission / execution / venue-gateway / reconciliation / control-plane

它不负责 Health / Metrics / Alert / Recovery，职责保持干净。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models.dependency import ServiceDependency
from ..models.service import ServiceIdentity


@dataclass(frozen=True)
class RegisteredService:

    identity: ServiceIdentity

    metadata: dict[str, str] = field(default_factory=dict)


class ServiceRegistry:

    def __init__(self) -> None:

        self._services: dict[
            str,
            RegisteredService,
        ] = {}

    def register(
        self,
        service: RegisteredService,
    ) -> None:

        self._services[
            service.identity.service_id
        ] = service

    def get(
        self,
        service_id: str,
    ) -> RegisteredService | None:

        return self._services.get(service_id)

    def all(self) -> list[RegisteredService]:

        return list(self._services.values())

    def contains(
        self,
        service_id: str,
    ) -> bool:

        return service_id in self._services


def validate_dependency(
    dependency: ServiceDependency,
    registry: ServiceRegistry,
) -> bool:

    """验证依赖两端的服务都已注册（spec section 19）。

    例如 strategy-runtime -> risk-engine，两个服务都必须存在。
    """

    return (
        registry.contains(
            dependency.source_service
        )
        and
        registry.contains(
            dependency.target_service
        )
    )
