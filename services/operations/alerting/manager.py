"""Alert manager (Commit 27 Part 1.3, spec sections 18-26).

AlertManager 负责编排：

    Rule Evaluation -> Dedup -> Suppression -> Duration ->
    Flapping -> Storm Protection -> Routing -> Alert Lifecycle

架构边界（spec section 29）：

    Alert 是"发现异常"，不是"执行交易控制"。

    Kill / Pause / Freeze / Failover / Recovery 仍由 Commit 26
    的 Control Plane 执行。Alert Engine 只负责 Detect / Classify /
    Deduplicate / Route / Correlate，绝不直接 Kill / 下单 / 改 Position / 改 Ledger。
"""

from __future__ import annotations

from collections import deque
from dataclasses import replace
from datetime import datetime, timezone
from typing import Callable

from ..models.dependency import ServiceDependency
from .alert import Alert
from .dedup import (
    AlertDeduplicator,
    AlertFingerprint,
    AlertStormProtector,
)
from .evaluator import AlertRuleEvaluator
from .models import AlertState
from .router import AlertRouter
from .rule import AlertRule
from .severity import AlertSeverity


class FlappingDetector:
    """Alert Flapping Detection（spec section 26）。

    一分钟内 FIRING -> RESOLVED -> FIRING -> RESOLVED 循环超过阈值
    即为 Flapping。此时应提升 severity（例如 WARNING -> ERROR），
    避免系统反复抖动却一直被当作普通问题。
    """

    def __init__(
        self,
        max_resolves_per_window: int = 3,
        window_seconds: float = 60.0,
        clock: Callable[[], datetime] | None = None,
    ) -> None:

        self.max_resolves_per_window = max_resolves_per_window

        self.window_seconds = window_seconds

        self._clock = clock or (
            lambda: datetime.now(timezone.utc)
        )

        self._resolves: dict[str, deque[datetime]] = {}

    def record_resolve(
        self,
        fingerprint: str,
    ) -> None:

        now = self._clock()

        events = self._resolves.setdefault(
            fingerprint,
            deque(),
        )

        while (
            events
            and (
                now - events[0]
            ).total_seconds() > self.window_seconds
        ):
            events.popleft()

        events.append(now)

    def is_flapping(
        self,
        fingerprint: str,
    ) -> bool:

        events = self._resolves.get(
            fingerprint,
            deque(),
        )

        return (
            len(events)
            > self.max_resolves_per_window
        )


class AlertManager:

    def __init__(
        self,
        evaluator: AlertRuleEvaluator,
        deduplicator: AlertDeduplicator,
        router: AlertRouter,
        storm_protector: AlertStormProtector | None = None,
        flapping_detector: FlappingDetector | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:

        self.evaluator = evaluator

        self.deduplicator = deduplicator

        self.router = router

        self._clock = clock or (
            lambda: datetime.now(timezone.utc)
        )

        self.storm_protector = (
            storm_protector
            or AlertStormProtector(clock=self._clock)
        )

        self.flapping_detector = (
            flapping_detector
            or FlappingDetector(clock=self._clock)
        )

        self._alerts: dict[str, Alert] = {}

        self._dependencies: list[ServiceDependency] = []

        self._unhealthy_services: set[str] = set()

        self._pending_since: dict[str, datetime] = {}

        self._suppressions: dict[str, str] = {}

    # ---------------------------------------------------------------
    # Suppression（spec sections 20-22）
    # ---------------------------------------------------------------

    def register_dependency(
        self,
        dependency: ServiceDependency,
    ) -> None:
        """注册服务依赖。上游（target）不健康时抑制下游告警。"""

        self._dependencies.append(dependency)

    def mark_unhealthy(
        self,
        service_id: str,
    ) -> None:
        """标记服务不健康（例如 event-bus UNHEALTHY）。"""

        self._unhealthy_services.add(service_id)

    def mark_healthy(
        self,
        service_id: str,
    ) -> None:
        """标记服务恢复健康。"""

        self._unhealthy_services.discard(service_id)

    def is_suppressed(
        self,
        fingerprint: str,
    ) -> str | None:
        """返回抑制该 fingerprint 的上游服务；未抑制返回 None。"""

        return self._suppressions.get(fingerprint)

    # ---------------------------------------------------------------
    # Evaluation（spec section 18）
    # ---------------------------------------------------------------

    def evaluate(
        self,
        rule: AlertRule,
        value: float,
        service_id: str | None = None,
        labels: dict[str, str] | None = None,
    ) -> str | None:
        """评估一条规则。

        返回新触发的 Alert fingerprint；未触发 / 重复 / 被抑制 /
        正在等待 duration 窗口 / 处于 storm suppression 时返回 None。
        """

        labels = labels or {}

        fingerprint = AlertFingerprint.build(
            rule.rule_id,
            service_id,
            labels,
        )

        triggered = self.evaluator.evaluate(
            rule,
            value,
        )

        if not triggered:
            # 条件恢复：结束 pending 窗口，释放 dedup，记录 resolve
            self._pending_since.pop(
                fingerprint,
                None,
            )

            self._suppressions.pop(
                fingerprint,
                None,
            )

            if self.deduplicator.is_duplicate(
                fingerprint
            ):
                self.flapping_detector.record_resolve(
                    fingerprint
                )

            self.deduplicator.resolve(
                fingerprint
            )

            return None

        # Suppression（spec section 22）：上游不健康 -> 下游告警抑制
        suppressed_by = self._suppressed_by(
            rule,
            service_id,
        )

        if suppressed_by is not None:
            self._pending_since.pop(
                fingerprint,
                None,
            )

            self._suppressions[
                fingerprint
            ] = suppressed_by

            return None

        # Duration / For（spec section 24）：条件需持续 N 秒才触发
        if rule.duration_seconds > 0:
            if fingerprint not in self._pending_since:
                self._pending_since[
                    fingerprint
                ] = self._clock()

                return None

            elapsed = (
                self._clock()
                - self._pending_since[fingerprint]
            ).total_seconds()

            if elapsed < rule.duration_seconds:
                return None

        # Storm protection（spec section 23）
        if self.storm_protector.suppression_mode:
            return None

        # Dedup（spec sections 13-15）
        if self.deduplicator.is_duplicate(
            fingerprint
        ):
            return None

        # 真正触发时清除历史抑制标记
        self._suppressions.pop(
            fingerprint,
            None,
        )

        self.deduplicator.register(
            fingerprint
        )

        self.storm_protector.record()

        return fingerprint

    # ---------------------------------------------------------------
    # Flapping（spec section 26）
    # ---------------------------------------------------------------

    def is_flapping(
        self,
        fingerprint: str,
    ) -> bool:
        """最近窗口内该 alert 是否发生 Flapping。"""

        return self.flapping_detector.is_flapping(
            fingerprint
        )

    def escalated_severity(
        self,
        fingerprint: str,
        severity: AlertSeverity,
    ) -> AlertSeverity:
        """Flapping 时提升 severity（例如 WARNING -> ERROR）。"""

        if not self.flapping_detector.is_flapping(
            fingerprint
        ):
            return severity

        if severity == AlertSeverity.EMERGENCY:
            return severity

        return AlertSeverity(
            int(severity) + 1
        )

    # ---------------------------------------------------------------
    # Alert Lifecycle（spec sections 5, 19）
    # ---------------------------------------------------------------

    def track(
        self,
        alert: Alert,
    ) -> None:
        """登记已创建的 Alert（供生命周期管理）。"""

        self._alerts[alert.alert_id] = alert

    def get(
        self,
        alert_id: str,
    ) -> Alert | None:

        return self._alerts.get(alert_id)

    def all_alerts(self) -> tuple[Alert, ...]:

        return tuple(self._alerts.values())

    def acknowledge(
        self,
        alert_id: str,
    ) -> Alert | None:
        """FIRING -> ACKNOWLEDGED。"""

        alert = self._alerts.get(alert_id)

        if (
            alert is None
            or alert.state != AlertState.FIRING
        ):
            return None

        updated = replace(
            alert,
            state=AlertState.ACKNOWLEDGED,
        )

        self._alerts[alert_id] = updated

        return updated

    def resolve_alert(
        self,
        alert_id: str,
    ) -> Alert | None:
        """-> RESOLVED。"""

        alert = self._alerts.get(alert_id)

        if (
            alert is None
            or alert.state == AlertState.RESOLVED
        ):
            return None

        updated = replace(
            alert,
            state=AlertState.RESOLVED,
            resolved_at=self._clock(),
        )

        self._alerts[alert_id] = updated

        return updated

    def suppress_alert(
        self,
        alert_id: str,
    ) -> Alert | None:
        """FIRING -> SUPPRESSED（例如告警风暴期间）。"""

        alert = self._alerts.get(alert_id)

        if alert is None:
            return None

        updated = replace(
            alert,
            state=AlertState.SUPPRESSED,
        )

        self._alerts[alert_id] = updated

        return updated

    # ---------------------------------------------------------------
    # Internal
    # ---------------------------------------------------------------

    def _suppressed_by(
        self,
        rule: AlertRule,
        service_id: str | None,
    ) -> str | None:
        """判断规则告警是否被上游故障抑制（spec section 22）。

        例如 risk -> event-bus 依赖，event-bus UNHEALTHY 时
        risk 的 service-unavailable 被 SUPPRESSED 并标记 suppressed_by=event-bus。
        """

        if service_id is None:
            return None

        for dependency in self._dependencies:

            if (
                dependency.source_service == service_id
                and dependency.required
                and (
                    dependency.target_service
                    in self._unhealthy_services
                )
            ):
                return dependency.target_service

        return None
