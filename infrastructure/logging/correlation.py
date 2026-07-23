"""
Request correlation identifier.
"""

import uuid


class CorrelationManager:

    def generate(self):
        return str(
            uuid.uuid4()
        )