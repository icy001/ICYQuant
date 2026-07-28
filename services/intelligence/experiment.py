from dataclasses import dataclass


@dataclass
class Experiment:

    experiment_id: str

    name: str

    status: str
