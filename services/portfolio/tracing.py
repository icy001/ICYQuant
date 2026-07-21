"""
Distributed tracing.
"""

import uuid


class TraceContext:

    def create(self):

        return str(
            uuid.uuid4()
        )