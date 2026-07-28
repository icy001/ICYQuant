from services.circuit_breaker import *


def test_circuit_breaker():
    service = CircuitBreakerService(
        CircuitBreakerManager(
            FailureDetector(),
            CircuitStateMachine(),
            RecoveryController()
        )
    )

    result = service.failure(
        FailureRecord(
            "RISK_SERVICE",
            5,
            1000
        ),
        CircuitConfig(
            5,
            60
        )
    )

    assert result == CircuitState.OPEN

    recovered = service.recover()

    assert recovered == CircuitState.HALF_OPEN
