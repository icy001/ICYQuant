from dataclasses import dataclass


@dataclass
class Feature:

    feature_id: str
    name: str
    enabled: bool
