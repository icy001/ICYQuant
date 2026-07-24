from dataclasses import dataclass


@dataclass
class Symbol:

    code: str

    exchange: str

    asset_type: str