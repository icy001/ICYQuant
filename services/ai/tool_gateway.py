"""
Tool gateway layer.
"""


class ToolGateway:

    def __init__(
        self,
        registry,
        permission,
    ):

        self.registry = registry

        self.permission = permission

    def execute(
        self,
        role,
        tool_name,
        arguments,
    ):

        if not self.permission.allowed(
            role,
            tool_name,
        ):

            raise PermissionError(
                "Tool access denied"
            )

        tool = self.registry.get(
            tool_name
        )

        return tool.execute(
            arguments
        )