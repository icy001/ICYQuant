"""
Log handlers package.

Exports all handler implementations
for the ICYQuant logging infrastructure.

Handler types:
- ConsoleHandler: stdout output
- FileHandler: file output
- RotatingFileHandler: rotating file output
- KafkaLogHandler: Kafka topic output
- ElasticsearchHandler: ES index output
- NullHandler: no-op (for testing)
"""

from .base import LogHandler
from .console import ConsoleHandler
from .elasticsearch import ElasticsearchHandler
from .file import FileHandler
from .kafka import KafkaLogHandler
from .null import NullHandler
from .rotating import RotatingFileHandler

__all__ = [
    "LogHandler",
    "ConsoleHandler",
    "FileHandler",
    "RotatingFileHandler",
    "KafkaLogHandler",
    "ElasticsearchHandler",
    "NullHandler",
]
