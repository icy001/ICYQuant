from dataclasses import dataclass


@dataclass
class Request:

    path: str

    method: str

    payload: dict

    headers: dict