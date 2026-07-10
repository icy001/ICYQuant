from services.observability import (
    ObservabilityConfig,
    ObservabilitySettings,
)


def test_default_config():
    config = ObservabilityConfig()
    assert (
        config.service_name
    )
    assert (
        config.tracing_enabled
        is True
    )


def test_custom_settings():
    settings = ObservabilitySettings(
        service_name="ledger",
        environment="production",
        log_level="INFO",
        tracing_enabled=True,
        metrics_enabled=True,
    )
    config = ObservabilityConfig(
        settings
    )
    assert (
        config.service_name
        ==
        "ledger"
    )