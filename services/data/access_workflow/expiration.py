"""
Access expiration.
"""

from datetime import datetime


class ExpirationPolicy:
    def expired(
        self,
        expire_at,
    ):
        return datetime.now() > expire_at