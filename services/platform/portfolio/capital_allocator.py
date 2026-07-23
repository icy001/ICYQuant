"""
Capital allocation engine.
"""


class CapitalAllocator:

    def allocate(
        self,
        capital,
        opportunities,
    ):

        return {
            "capital":
                capital,
            "allocation":
                opportunities,
        }