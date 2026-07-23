from infrastructure import ProductionRuntime


def test_runtime():

    runtime = ProductionRuntime()

    result = runtime.status()

    assert result["runtime"] == "active"