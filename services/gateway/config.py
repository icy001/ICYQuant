from dataclasses import dataclass


@dataclass
class GatewayConfig:

    host: str

    port: int

    timeout: int = 30