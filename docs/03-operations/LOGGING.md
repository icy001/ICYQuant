# ICYQuant Logging

> 本文档描述 ICYQuant 的日志体系。

---

## 1. 日志原则

```text
结构化（JSON）
    +
可关联（trace_id / correlation_id）
    +
分级（DEBUG / INFO / WARNING / ERROR / CRITICAL）
    +
可检索（集中收集）
```

---

## 2. 日志格式

- 默认结构化 JSON
- 每个请求 / 事件携带 `trace_id`
- 交易链路携带 `correlation_id`

```json
{
  "timestamp": "...",
  "level": "INFO",
  "logger": "services.risk",
  "trace_id": "...",
  "correlation_id": "...",
  "message": "..."
}
```

---

## 3. 日志分类

| 类型 | 说明 |
|------|------|
| 应用日志 | 业务操作、服务事件 |
| 审计日志 | 敏感 / 关键操作（不可变） |
| 访问日志 | API 请求 |
| 安全日志 | 认证、授权失败 |

---

## 4. 配置

- 级别通过配置 / 环境变量控制
- 生产建议 INFO 及以上
- 敏感信息脱敏（密码、Token 不落日志）

---

## 5. 日志运维

- 集中收集（ELK / Loki 等）
- 按 trace_id 全链路检索
- 日志保留策略（满足审计要求）

---

## 6. 相关文档

- 监控：[MONITORING.md](./MONITORING.md)
- 审计与追踪：[../02-technical/AUDIT_TRACE.md](../02-technical/AUDIT_TRACE.md)
- 事故响应：[INCIDENT_RESPONSE.md](./INCIDENT_RESPONSE.md)
