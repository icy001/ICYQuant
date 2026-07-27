from dataclasses import dataclass


@dataclass
class FactorExposure:
    factor_name: str
    exposure: float