from services.observability.prometheus import (
    record_order,
    export_metrics,
)


def test_prometheus_export():
    record_order()
    result = export_metrics()
    assert isinstance(
        result,
        bytes
    )