from dataclasses import dataclass


@dataclass
class UserProfile:

    user_id: str

    display_name: str

    timezone: str