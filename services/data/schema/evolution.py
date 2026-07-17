"""
Schema evolution checker.
"""


class SchemaEvolutionChecker:
    def compatible(
        self,
        old_schema,
        new_schema,
    ):
        old_fields = {field.name for field in old_schema.fields}
        new_fields = {field.name for field in new_schema.fields}
        return old_fields.issubset(new_fields)