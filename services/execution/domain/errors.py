from __future__ import annotations


class ExecutionError(Exception):
    pass


class ExecutionAdapterError(
    ExecutionError
):
    pass


class ExecutionSubmissionError(
    ExecutionAdapterError
):
    pass


class ExecutionConnectionError(
    ExecutionAdapterError
):
    pass


class ExecutionTimeoutError(
    ExecutionAdapterError
):
    pass


class ExecutionConsumerError(
    RuntimeError
):
    retryable = True


class NonRetryableExecutionError(
    ExecutionConsumerError
):
    retryable = False


class RetryableExecutionError(
    ExecutionConsumerError
):
    retryable = True
