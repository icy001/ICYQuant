"""
Tool execution engine.
"""


class ToolExecutor:

    def __init__(
        self,
        handlers,
    ):

        self.handlers = handlers

    def execute(
        self,
        name,
        arguments,
    ):

        handler = self.handlers.get(
            name,
        )

        if handler is None:

            raise ValueError(
                f"Unknown tool: {name}"
            )

        return handler(
            **arguments
        )