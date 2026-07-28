from dataclasses import dataclass


@dataclass
class Experiment:

    experiment_id: str

    parameters: dict

    result: dict
