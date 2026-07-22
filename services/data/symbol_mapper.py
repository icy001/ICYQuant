"""
Unified symbol mapper.
"""


class SymbolMapper:

    def __init__(self):

        self._mapping = {}

    def register(
        self,
        vendor_symbol,
        internal_symbol,
    ):

        self._mapping[
            vendor_symbol
        ] = internal_symbol

    def resolve(
        self,
        vendor_symbol,
    ):

        return self._mapping.get(
            vendor_symbol,
            vendor_symbol,
        )