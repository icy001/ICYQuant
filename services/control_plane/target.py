"""Control target model and fail-closed target resolution (Commit 29 Part 1.1 §10-11, §34).

A control command must name its target explicitly: *who*, in *which
environment*, against *which instance*, performing *what* action. Production
may run OMS / OMS-01 / OMS-02 / OMS-03 at once, so ``trading:pause`` alone is
never enough (§11). Unknown targets are rejected — the Control Plane fails
closed (§34-35).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .errors import TargetNotFound


@dataclass(frozen=True)
class ControlTarget:
    service: str
    instance: str | None = None
    environment: str = "production"


class TargetResolver(Protocol):
    """Resolves a ``ControlTarget``; raises ``TargetNotFound`` when unknown (§34)."""

    def resolve(self, target: ControlTarget) -> None: ...


DEFAULT_CONTROL_TARGETS: frozenset[tuple[str, str, str]] = frozenset(
    {
        ("production", "oms", "oms-primary"),
        ("production", "oms", "oms-secondary"),
        ("production", "risk", "risk-01"),
        ("production", "position", "position-primary"),
        ("production", "ledger", "ledger-primary"),
        ("production", "strategy", "strategy-01"),
    }
)


class StaticTargetResolver:
    """Resolves targets against a fixed known set; unknown -> ``TargetNotFound``.

    The default set only contains production targets so that a request that
    mixes ``environment=production`` with an unlisted instance (e.g. a
    ``test-oms`` instance) is rejected instead of "best-effort executed".
    """

    def __init__(
        self,
        known: set[tuple[str, str, str]] | None = None,
    ) -> None:
        self._known = (
            set(known) if known is not None else set(DEFAULT_CONTROL_TARGETS)
        )

    def resolve(self, target: ControlTarget) -> None:
        key = (target.environment, target.service, target.instance or "")
        if key not in self._known:
            raise TargetNotFound(
                f"control target not found: "
                f"environment={target.environment} "
                f"service={target.service} "
                f"instance={target.instance or '-'}"
            )
