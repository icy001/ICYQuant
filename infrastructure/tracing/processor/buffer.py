"""Memory and disk buffer for span recovery."""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, List, Optional


class SpanBuffer:
    """
    Span buffer with memory and disk fallback.

    Provides a multi-tier buffer:
    1. Memory buffer (fast, volatile)
    2. Disk buffer (persistent, for recovery)

    Features:
    - FIFO overflow from memory to disk
    - Recovery queue on restart
    - Overflow protection
    - Automatic recovery

    Usage:
        buffer = SpanBuffer(memory_size=2048, disk_path="/tmp/traces")
        buffer.put(span)
        batch = buffer.get_batch(512)
    """

    def __init__(
        self,
        memory_size: int = 2048,
        disk_path: Optional[str] = None,
        max_disk_size: int = 10000,
    ) -> None:
        self._memory_size = memory_size
        self._disk_path = disk_path or tempfile.gettempdir()
        self._max_disk_size = max_disk_size
        self._memory: List[Any] = []
        self._disk_count: int = 0
        self._total_buffered: int = 0
        self._total_recovered: int = 0

    @property
    def memory_size(self) -> int:
        return len(self._memory)

    @property
    def disk_count(self) -> int:
        return self._disk_count

    def put(self, span: Any) -> bool:
        """Add a span to the buffer."""
        if len(self._memory) < self._memory_size:
            self._memory.append(span)
            self._total_buffered += 1
            return True

        if self._disk_count < self._max_disk_size:
            self._write_to_disk(span)
            self._total_buffered += 1
            return True

        return False

    def get_batch(self, batch_size: int = 512) -> List[Any]:
        """Get a batch from memory, refilling from disk."""
        batch = self._memory[:batch_size]
        self._memory = self._memory[batch_size:]

        refill_needed = self._memory_size - len(self._memory)
        if refill_needed > 0 and self._disk_count > 0:
            disk_spans = self._read_from_disk(refill_needed)
            self._memory.extend(disk_spans)

        return batch

    def _write_to_disk(self, span: Any) -> None:
        """Write span to disk buffer."""
        try:
            filename = os.path.join(
                self._disk_path,
                f"icyquant_span_{self._disk_count}.json",
            )
            data = span.to_dict() if hasattr(span, "to_dict") else str(span)
            with open(filename, "w") as f:
                json.dump(data, f, default=str)
            self._disk_count += 1
        except Exception:
            pass

    def _read_from_disk(self, count: int) -> List[Any]:
        """Read spans from disk buffer."""
        spans = []
        try:
            files = sorted(
                f for f in os.listdir(self._disk_path)
                if f.startswith("icyquant_span_")
            )
            for filename in files[:count]:
                filepath = os.path.join(self._disk_path, filename)
                with open(filepath, "r") as f:
                    data = json.load(f)
                spans.append(data)
                os.remove(filepath)
                self._disk_count -= 1
                self._total_recovered += 1
        except Exception:
            pass
        return spans

    def recover(self) -> List[Any]:
        """Recover all spans from disk."""
        return self._read_from_disk(self._max_disk_size)

    def drain(self) -> List[Any]:
        """Drain all spans from memory and disk."""
        memory = self._memory
        self._memory = []
        disk = self._read_from_disk(self._max_disk_size)
        return memory + disk

    def clear(self) -> None:
        """Clear all buffers."""
        self._memory.clear()
        try:
            files = sorted(
                f for f in os.listdir(self._disk_path)
                if f.startswith("icyquant_span_")
            )
            for filename in files:
                os.remove(os.path.join(self._disk_path, filename))
        except Exception:
            pass
        self._disk_count = 0

    def get_stats(self) -> dict:
        return {
            "memory_size": self.memory_size,
            "memory_max": self._memory_size,
            "disk_count": self._disk_count,
            "disk_max": self._max_disk_size,
            "total_buffered": self._total_buffered,
            "total_recovered": self._total_recovered,
        }
