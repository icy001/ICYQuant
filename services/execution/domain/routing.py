from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExecutionRoutingPolicy:
    preferred_venue: str | None = None

    allowed_venues: tuple[str, ...] = ()

    fallback_venues: tuple[str, ...] = ()

    metadata: dict[str, object] = field(
        default_factory=dict
    )

    def validate(self) -> None:
        if (
            self.preferred_venue is not None
            and self.preferred_venue not in self.allowed_venues
            and self.allowed_venues
        ):
            raise ValueError(
                "preferred venue must be in allowed venues"
            )
