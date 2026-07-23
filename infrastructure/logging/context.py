"""
Logging execution context.
"""


class LogContext:

    def __init__(self):
        self.data = {}

    def set(
        self,
        key,
        value,
    ):
        self.data[key] = value

    def get_all(self):
        return self.data