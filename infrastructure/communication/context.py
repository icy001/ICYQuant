"""
Request context propagation.
"""


class RequestContext:

    def __init__(self):
        self.values = {}

    def set(
        self,
        key,
        value,
    ):
        self.values[key] = value

    def get(
        self,
        key,
    ):
        return self.values.get(key)