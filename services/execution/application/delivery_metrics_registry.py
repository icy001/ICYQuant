from __future__ import annotations

from services.execution.domain.delivery_metrics import (
    DeliveryMetrics,
)


class DeliveryMetricsRegistry:

    def __init__(self) -> None:

        self._metrics: dict[
            str,
            DeliveryMetrics,
        ] = {}

    def get(
        self,
        consumer_id: str,
    ) -> DeliveryMetrics:

        return self._metrics.setdefault(
            consumer_id,
            DeliveryMetrics(),
        )
