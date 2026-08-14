# ICYQuant Monitoring

> 本文档描述 ICYQuant 的监控体系。

---

## 1. 监控层次

### 1.1 System（系统）

```text
CPU
Memory
Disk
Network
Container Health
```

### 1.2 Application（应用）

```text
API Latency
Error Rate
Request Rate
Event Processing Rate
Queue Lag
```

### 1.3 Trading（交易）

```text
Signal Count
Approved Signal Count
Risk Reject Count
Order Count
Execution Count
Fill Rate
Reject Rate
```

### 1.4 Risk（风险）

```text
Exposure
Drawdown
Risk Decision
Recovery Request
Reconciliation Exception
```

---

## 2. 指标暴露

- `/metrics` 端点暴露 Prometheus 指标
- 结构化日志携带 trace_id 便于链路追踪
- 详见 [LOGGING.md](./LOGGING.md)

---

## 3. 告警

- 基于指标阈值触发
- 告警接入事故管理（Incident）生命周期
- 严重度分级（CRITICAL / WARNING / INFO）

---

## 4. 关键告警项

| 指标 | 建议阈值（示例） | 严重度 |
|------|------------------|--------|
| Error Rate | > 5% | WARNING |
| API Latency P99 | > 500ms | WARNING |
| Queue Lag | 持续增长 | WARNING |
| Reconciliation Exception | > 0 | CRITICAL |
| 数据不一致 | 出现即告警 | CRITICAL |

---

## 5. 监控体系

```text
指标采集（/metrics）
    ↓
告警引擎
    ↓
事故管理（Incident）
    ↓
响应（Runbook）
    ↓
复盘（Postmortem）
```

---

## 6. 相关文档

- 日志：[LOGGING.md](./LOGGING.md)
- 事故响应：[INCIDENT_RESPONSE.md](./INCIDENT_RESPONSE.md)
- 生产运行手册：[PRODUCTION_RUNBOOK.md](./PRODUCTION_RUNBOOK.md)
