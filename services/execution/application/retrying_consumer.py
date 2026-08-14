from __future__ import annotations

from datetime import datetime

from services.execution.application.event_consumer import (
    ExecutionEventConsumer,
)
from services.execution.domain.consumer import (
    ConsumerOffset,
)
from services.execution.domain.dead_letter import (
    DeadLetterEvent,
)
from services.execution.domain.delivery import (
    DeliveryAttempt,
    DeliveryStatus,
)
from services.execution.domain.retry import (
    RetryPolicy,
)
from services.execution.ports.consumer_offset_store import (
    ConsumerOffsetStore,
)
from services.execution.ports.dead_letter_store import (
    DeadLetterStore,
)
from services.execution.ports.delivery_store import (
    DeliveryStore,
)
from services.execution.ports.event_store import (
    ExecutionEventStore,
)


class RetryingExecutionConsumer:

    def __init__(
        self,
        consumer: ExecutionEventConsumer,
        event_store: ExecutionEventStore,
        offset_store: ConsumerOffsetStore,
        dead_letter_store: DeadLetterStore,
        retry_policy: RetryPolicy | None = None,
        delivery_store: DeliveryStore | None = None,
    ) -> None:

        self._consumer = consumer
        self._event_store = event_store
        self._offset_store = offset_store
        self._dead_letter_store = (
            dead_letter_store
        )
        self._delivery_store = delivery_store

        self._retry_policy = (
            retry_policy
            or RetryPolicy()
        )

        self._attempts: dict[
            tuple[str, str, int],
            int,
        ] = {}

    def consume(
        self,
        stream_id: str,
    ) -> int:

        current = (
            self._offset_store.get(
                self._consumer.consumer_id,
                stream_id,
            )
        )

        after_sequence = (
            current.sequence
            if current is not None
            else 0
        )

        events = self._event_store.stream(
            stream_id,
            after_sequence=after_sequence,
        )

        last_sequence = after_sequence

        for event in events:

            success = self._deliver(
                event,
                stream_id,
            )

            if not success:
                break

            self._offset_store.save(
                ConsumerOffset(
                    consumer_id=(
                        self._consumer.consumer_id
                    ),
                    stream_id=stream_id,
                    sequence=event.sequence,
                )
            )

            last_sequence = event.sequence

        return last_sequence

    def _deliver(
        self,
        event,
        stream_id: str,
    ) -> bool:

        key = (
            self._consumer.consumer_id,
            stream_id,
            event.sequence,
        )

        attempt = (
            self._attempts.get(key, 0)
            + 1
        )

        self._attempts[key] = attempt

        self._record_delivery(
            event,
            stream_id,
            attempt,
            DeliveryStatus.PROCESSING,
            error=None,
        )

        try:

            self._consumer.handle(event)

            self._record_delivery(
                event,
                stream_id,
                attempt,
                DeliveryStatus.DELIVERED,
                error=None,
            )

            return True

        except Exception as exc:

            retryable = getattr(
                exc,
                "retryable",
                True,
            )

            if (
                not retryable
                or attempt
                >= self._retry_policy.max_attempts
            ):

                self._record_delivery(
                    event,
                    stream_id,
                    attempt,
                    DeliveryStatus.DEAD_LETTERED,
                    error=str(exc),
                )

                self._dead_letter_store.save(
                    DeadLetterEvent(
                        event=event,
                        consumer_id=(
                            self._consumer.consumer_id
                        ),
                        attempts=attempt,
                        error=str(exc),
                        created_at=datetime.now(),
                    )
                )

                return False

            self._record_delivery(
                event,
                stream_id,
                attempt,
                DeliveryStatus.RETRYING,
                error=str(exc),
            )

            return False

    def _record_delivery(
        self,
        event,
        stream_id: str,
        attempt: int,
        status: DeliveryStatus,
        error: str | None,
    ) -> None:

        if self._delivery_store is None:
            return

        self._delivery_store.save(
            DeliveryAttempt(
                consumer_id=(
                    self._consumer.consumer_id
                ),
                stream_id=stream_id,
                sequence=event.sequence,
                attempt=attempt,
                status=status,
                error=error,
            )
        )
