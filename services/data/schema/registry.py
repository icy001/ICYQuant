"""
Schema registry.
"""


class SchemaRegistry:
    def __init__(self):
        self.schemas = {}

    def register(
        self,
        schema,
    ):
        key = (schema.name, schema.version)
        self.schemas[key] = schema

    def get(
        self,
        name,
        version,
    ):
        return self.schemas.get((name, version))