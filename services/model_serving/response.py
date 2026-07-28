from dataclasses import dataclass


@dataclass
class PredictionResponse:

    prediction: float

    signal: str
