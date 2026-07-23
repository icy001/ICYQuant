from infra.monitoring.system_monitor import (
    SystemMonitor,
)


def test_monitor():

    monitor = SystemMonitor()

    result = monitor.collect()


    assert result["cpu"] == "ok"