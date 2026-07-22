"""
Schema registry.
"""


class SchemaRegistry:

    def __init__(self):

        self._schemas = {}

    def register(
        self,
        name,
        schema,
    ):

        self._schemas[name] = schema

    def get(
        self,
        name,
    ):

        return self._schemas.get(
            name,
        )