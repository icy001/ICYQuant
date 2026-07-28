from dataclasses import dataclass


@dataclass
class Dataset:

    dataset_id: str

    features: list

    labels: list
