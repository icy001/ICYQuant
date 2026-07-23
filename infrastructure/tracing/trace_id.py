"""
Trace identifier generator.
"""

import uuid


class TraceIdGenerator:

    def generate(self):
        return str(
            uuid.uuid4()
        )