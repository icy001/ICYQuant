from dataclasses import dataclass


@dataclass
class RegistrationRequest:
    service_name: str
    host: str
    port: int
