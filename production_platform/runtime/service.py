from dataclasses import dataclass


@dataclass
class Service:

    name: str

    version: str

    status: str = "STOPPED"