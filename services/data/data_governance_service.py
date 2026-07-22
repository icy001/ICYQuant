"""
Data governance service.
"""


class DataGovernanceService:

    def __init__(
        self,
        metadata_catalog,
        schema_registry,
        lineage,
    ):

        self.metadata_catalog = metadata_catalog

        self.schema_registry = schema_registry

        self.lineage = lineage

    def register_dataset(
        self,
        dataset,
        metadata,
        schema,
    ):

        self.metadata_catalog.register(
            dataset,
            metadata,
        )

        self.schema_registry.register(
            dataset,
            schema,
        )