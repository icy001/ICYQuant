from dataclasses import dataclass


@dataclass
class ServiceInstance:
    service_id: str
    service_name: str
    host: str
    port: int
    status: str
