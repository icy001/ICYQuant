"""
Exposure aggregator.
"""


class ExposureAggregator:

    def aggregate(
        self,
        exposures,
    ):

        result = {}

        for exposure in exposures:

            key = exposure.asset

            result[key] = (
                result.get(
                    key,
                    0,
                )
                +
                exposure.value
            )

        return result