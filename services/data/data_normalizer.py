"""
Market data normalizer.
"""


class DataNormalizer:

    def normalize(
        self,
        record,
    ):

        return {
            k.lower(): v
            for k, v in record.items()
        }