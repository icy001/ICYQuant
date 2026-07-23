from services.ai import (
    ToolPermission,
    ToolGateway,
)


class MockRegistry:

    def get(self, name):

        return MockTool()


class MockTool:

    def execute(self, arguments):

        return {"result": "ok"}


def test_tool_permission():

    permission = ToolPermission()

    permission.grant("admin", "market_data")

    assert permission.allowed("admin", "market_data")

    assert not permission.allowed("guest", "market_data")


def test_tool_gateway():

    permission = ToolPermission()

    permission.grant("admin", "market_data")

    gateway = ToolGateway(
        MockRegistry(),
        permission,
    )

    result = gateway.execute(
        "admin",
        "market_data",
        {},
    )

    assert result["result"] == "ok"