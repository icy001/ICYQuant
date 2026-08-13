"""Alert fingerprint & deduplication (Commit 27 Part 1.3, spec sections 13-15, 23).

Alert ID 必须稳定。不能每次检测都生成新 Alert，否则 Latency > 100
持续一分钟会产生 Alert 001/002/003... 最终形成 Alert Storm。

Fingerprint 由 rule_id + service_id + labels 的稳定组合构成：

    execution-latency-high + execution-01 + venue=NASDAQ
        -> 永远同一个 fingerprint
"""

from __future__ import annotations

import hashlib
from collections import deque
from datetime import datetime, timezone
from typing import Callable


class AlertFingerprint:

    @staticmethod
    def build(
        rule_id: str,
        service_id: str | None,
        labels: dict[str, str],
    ) -> str:

        label_text = "|".join(
            f"{key}={value}"
            for key, value
            in sorted(labels.items())
        )

        raw = (
            f"{rule_id}|"
            f"{service_id}|"
            f"{label_text}"
        )

        return hashlib.sha256(
            raw.encode()
        ).hexdigest()


class AlertDeduplicator:

    def __init__(self) -> None:

        self._active: set[str] = set()

    def is_duplicate(
        self,
        fingerprint: str,
    ) -> bool:

        return fingerprint in self._active

    def register(
        self,
        fingerprint: str,
    ) -> None:

        self._active.add(fingerprint)

    def resolve(
        self,
        fingerprint: str,
    ) -> None:

        self._active.discard(
            fingerprint
        )


class AlertStormProtector:
    """Alert Storm Protection（spec section 23）。

    例如 100 alerts / minute。超过则检测到 Alert Storm（CRITICAL），
    并进入 SUPPRESSION MODE，避免运营系统自己被打爆。
    """

    def __init__(
        self,
        max_alerts_per_window: int = 100,
        window_seconds: float = 60.0,
        clock: Callable[[], datetime] | None = None,
    ) -> None:

        self.max_alerts_per_window = max_alerts_per_window

        self.window_seconds = window_seconds

        self._clock = clock or (
            lambda: datetime.now(timezone.utc)
        )

        self._firings: deque[datetime] = deque()

        self._storm_detected = False

        self._suppression_mode = False

    @property
    def storm_detected(self) -> bool:

        return self._storm_detected

    @property
    def suppression_mode(self) -> bool:

        return self._suppression_mode

    def record(self) -> bool:
        """记录一次新 alert。

        返回 True 表示本次记录触发了 Storm Detection，
        并进入 SUPPRESSION MODE。
        """

        now = self._clock()

        while (
            self._firings
            and (
                now - self._firings[0]
            ).total_seconds() > self.window_seconds
        ):
            self._firings.popleft()

        self._firings.append(now)

        if (
            len(self._firings)
            > self.max_alerts_per_window
        ):
            self._storm_detected = True

            self._suppression_mode = True

            return True

        return False

    def release(self) -> None:
        """退出 SUPPRESSION MODE（窗口清空 / 人工介入后）。"""

        self._storm_detected = False

        self._suppression_mode = False

        self._firings.clear()
