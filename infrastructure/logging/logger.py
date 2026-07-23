"""
Institutional structured logger.
"""

from datetime import datetime


class Logger:

    def __init__(self, name):
        self.name = name

    def _create_event(
        self,
        level,
        message,
        context=None,
    ):
        return {
            "service":
                self.name,
            "level":
                level,
            "message":
                message,
            "timestamp":
                datetime.utcnow().isoformat(),
            "context":
                context or {}
        }

    def info(
        self,
        message,
        context=None,
    ):
        return self._create_event(
            "INFO",
            message,
            context
        )

    def error(
        self,
        message,
        context=None,
    ):
        return self._create_event(
            "ERROR",
            message,
            context
        )