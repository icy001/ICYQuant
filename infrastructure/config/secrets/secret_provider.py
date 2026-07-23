"""
Secret management abstraction.
"""


class SecretProvider:

    def __init__(self):
        self.secrets = {}

    def set(
        self,
        key,
        value,
    ):
        self.secrets[key] = value

    def get(
        self,
        key,
    ):
        return self.secrets.get(key)