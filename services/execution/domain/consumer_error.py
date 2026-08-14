from __future__ import annotations


class ConsumerProcessingError(
    RuntimeError
):
    def __init__(
        self,
        consumer_id: str,
        sequence: int,
        cause: Exception,
    ) -> None:

        super().__init__(
            f"consumer '{consumer_id}' "
            f"failed at sequence "
            f"{sequence}: {cause}"
        )

        self.consumer_id = consumer_id
        self.sequence = sequence
        self.cause = cause
