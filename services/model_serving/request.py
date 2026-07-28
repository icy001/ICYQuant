from dataclasses import dataclass


@dataclass
class PredictionRequest:

    symbol: str

    features: dict
