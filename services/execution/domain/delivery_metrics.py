from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeliveryMetrics:

    delivered: int = 0

    failed: int = 0

    retried: int = 0

    dead_lettered: int = 0

    recovered: int = 0

    def record_success(self) -> None:
        self.delivered += 1

    def record_failure(self) -> None:
        self.failed += 1

    def record_retry(self) -> None:
        self.retried += 1

    def record_dead_letter(self) -> None:
        self.dead_lettered += 1

    def record_recovery(self) -> None:
        self.recovered += 1
