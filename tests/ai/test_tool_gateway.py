from services.ai import ToolPermission


def test_permission():

    permission = ToolPermission()

    permission.grant(
        "researcher",
        "market_data"
    )

    assert permission.allowed(
        "researcher",
        "market_data"
    )