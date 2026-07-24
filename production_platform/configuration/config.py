from dataclasses import dataclass


@dataclass
class Configuration:

    name: str

    value: object

    environment: str