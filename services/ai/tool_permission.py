"""
Tool permission control.
"""


class ToolPermission:

    def __init__(self):

        self._permissions = {}

    def grant(
        self,
        role,
        tool,
    ):

        self._permissions.setdefault(
            role,
            set()
        ).add(
            tool
        )

    def allowed(
        self,
        role,
        tool,
    ):

        return tool in self._permissions.get(
            role,
            set(),
        )