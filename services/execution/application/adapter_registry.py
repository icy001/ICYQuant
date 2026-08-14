from __future__ import annotations

from services.execution.ports.execution_adapter import (
    ExecutionAdapter,
)


class ExecutionAdapterRegistry:

    def __init__(self) -> None:
        self._adapters: dict[
            str,
            ExecutionAdapter,
        ] = {}

    def register(
        self,
        venue_id: str,
        adapter: ExecutionAdapter,
    ) -> None:

        if not venue_id:
            raise ValueError(
                "venue_id is required"
            )

        if venue_id in self._adapters:
            raise ValueError(
                f"adapter already registered: "
                f"{venue_id}"
            )

        self._adapters[
            venue_id
        ] = adapter

    def get(
        self,
        venue_id: str,
    ) -> ExecutionAdapter:

        try:
            return self._adapters[
                venue_id
            ]
        except KeyError:
            raise KeyError(
                f"execution adapter not found: "
                f"{venue_id}"
            )
