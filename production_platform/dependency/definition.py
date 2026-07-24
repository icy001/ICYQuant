from dataclasses import dataclass


@dataclass
class Dependency:

    name: str

    implementation: object

    scope: str