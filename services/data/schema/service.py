"""
Schema governance service.
"""


class SchemaGovernanceService:
    def __init__(
        self,
        registry,
        validator,
        evolution,
    ):
        self.registry = registry
        self.validator = validator
        self.evolution = evolution

    def register_schema(
        self,
        schema,
    ):
        self.registry.register(schema)