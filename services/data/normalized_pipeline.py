"""
Normalized market data pipeline.
"""


class NormalizedPipeline:

    def __init__(
        self,
        normalizer,
        mapper,
        converter,
        adjuster,
    ):

        self.normalizer = normalizer
        self.mapper = mapper
        self.converter = converter
        self.adjuster = adjuster

    def process(
        self,
        record,
    ):

        normalized = self.normalizer.normalize(
            record
        )

        normalized["symbol"] = self.mapper.resolve(
            normalized["symbol"]
        )

        return normalized