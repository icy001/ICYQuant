from dataclasses import dataclass


@dataclass
class ServiceInstance:
    service_name: str
    instance_id: str
    host: str
    port: int
    healthy: bool = True
