from dataclasses import dataclass
import time


@dataclass
class CacheEntry:

    key: str

    value: object

    created_at: float = time.time()