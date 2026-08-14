from services.execution.domain.errors import (
    ExecutionAdapterError,
    ExecutionConnectionError,
    ExecutionError,
    ExecutionSubmissionError,
    ExecutionTimeoutError,
)


def test_error_hierarchy():

    assert issubclass(
        ExecutionError,
        Exception,
    )
    assert issubclass(
        ExecutionAdapterError,
        ExecutionError,
    )
    assert issubclass(
        ExecutionSubmissionError,
        ExecutionAdapterError,
    )
    assert issubclass(
        ExecutionConnectionError,
        ExecutionAdapterError,
    )
    assert issubclass(
        ExecutionTimeoutError,
        ExecutionAdapterError,
    )


def test_adapter_errors_share_catchable_base():

    errors = [
        ExecutionSubmissionError("reject"),
        ExecutionConnectionError("offline"),
        ExecutionTimeoutError("timeout"),
    ]

    for error in errors:
        assert isinstance(
            error,
            ExecutionAdapterError,
        )
        assert isinstance(
            error,
            ExecutionError,
        )


def test_external_failure_can_be_caught_as_execution_error():

    try:
        raise ExecutionConnectionError(
            "connection lost"
        )
    except ExecutionError as exc:
        assert "connection lost" in str(exc)
