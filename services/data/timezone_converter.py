"""
Timezone converter.
"""

from datetime import timezone


class TimezoneConverter:

    def convert(
        self,
        timestamp,
        tz=timezone.utc,
    ):

        return timestamp.astimezone(
            tz
        )