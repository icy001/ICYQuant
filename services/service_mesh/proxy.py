from dataclasses import dataclass


@dataclass
class Proxy:

    service_name: str
    version: str
    status: str
