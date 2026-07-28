from dataclasses import dataclass


@dataclass
class ServiceIdentity:

    service_name: str
    certificate: str
