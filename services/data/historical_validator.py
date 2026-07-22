"""
Historical data validator.
"""


class HistoricalValidator:

    REQUIRED_FIELDS = {
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    def validate(
        self,
        records,
    ):

        for record in records:

            if not self.REQUIRED_FIELDS.issubset(
                record.keys(),
            ):

                return False

        return True