"""OrderMetrics — order lifecycle metrics."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class OrderMetrics:
    """Metrics for order lifecycle."""

    orders_created_total: int = 0
    orders_working_total: int = 0
    orders_filled_total: int = 0
    orders_cancelled_total: int = 0
    orders_rejected_total: int = 0
    orders_expired_total: int = 0
    orders_failed_total: int = 0

    # Latency (seconds)
    order_submission_latency_sum: float = 0.0
    order_submission_latency_count: int = 0
    ack_latency_sum: float = 0.0
    ack_latency_count: int = 0
    first_fill_latency_sum: float = 0.0
    first_fill_latency_count: int = 0
    full_fill_latency_sum: float = 0.0
    full_fill_latency_count: int = 0

    def record_created(self) -> None:
        self.orders_created_total += 1

    def record_working(self) -> None:
        self.orders_working_total += 1

    def record_filled(self) -> None:
        self.orders_filled_total += 1

    def record_cancelled(self) -> None:
        self.orders_cancelled_total += 1

    def record_rejected(self) -> None:
        self.orders_rejected_total += 1

    def record_expired(self) -> None:
        self.orders_expired_total += 1

    def record_submission_latency(self, latency: float) -> None:
        self.order_submission_latency_sum += latency
        self.order_submission_latency_count += 1

    def record_ack_latency(self, latency: float) -> None:
        self.ack_latency_sum += latency
        self.ack_latency_count += 1

    def record_first_fill_latency(self, latency: float) -> None:
        self.first_fill_latency_sum += latency
        self.first_fill_latency_count += 1

    def record_full_fill_latency(self, latency: float) -> None:
        self.full_fill_latency_sum += latency
        self.full_fill_latency_count += 1

    @property
    def avg_submission_latency(self) -> float:
        if self.order_submission_latency_count == 0:
            return 0
        return (self.order_submission_latency_sum
                / self.order_submission_latency_count)

    @property
    def avg_ack_latency(self) -> float:
        if self.ack_latency_count == 0:
            return 0
        return self.ack_latency_sum / self.ack_latency_count

    def to_dict(self) -> Dict:
        return {
            "orders_created_total": self.orders_created_total,
            "orders_working_total": self.orders_working_total,
            "orders_filled_total": self.orders_filled_total,
            "orders_cancelled_total": self.orders_cancelled_total,
            "orders_rejected_total": self.orders_rejected_total,
            "orders_expired_total": self.orders_expired_total,
            "orders_failed_total": self.orders_failed_total,
            "avg_submission_latency": self.avg_submission_latency,
            "avg_ack_latency": self.avg_ack_latency,
            "avg_first_fill_latency": (
                self.first_fill_latency_sum / self.first_fill_latency_count
                if self.first_fill_latency_count > 0 else 0
            ),
            "avg_full_fill_latency": (
                self.full_fill_latency_sum / self.full_fill_latency_count
                if self.full_fill_latency_count > 0 else 0
            ),
        }
