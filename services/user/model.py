from dataclasses import dataclass


@dataclass
class User:

    user_id: str

    username: str

    email: str

    status: str = "ACTIVE"