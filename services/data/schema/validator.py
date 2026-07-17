"""
Schema validator.
"""


class SchemaValidator:
    def validate(
        self,
        schema,
        payload,
    ):
        for field in schema.fields:
            if field.name not in payload and not field.nullable:
                return False
        return True