from dataclasses import dataclass


@dataclass
class AlphaExperiment:

    experiment_id: str

    factor_id: str

    result: dict
