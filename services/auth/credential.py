from dataclasses import dataclass


@dataclass
class Credential:

    username: str

    password_hash: str