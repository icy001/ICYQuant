# ICYQuant Backup & Recovery

> 本文档描述 ICYQuant 的备份与恢复体系。

---

## 1. 需要保护的数据

```text
Database
Configuration
Strategy Definitions
Risk Policies
Audit Logs
Event History
Research Results
```

---

## 2. 备份策略

| 数据 | 策略 |
|------|------|
| 数据库 | 定期全量 + WAL 归档 |
| 配置 | 版本控制 + 导出 |
| 审计日志 | 不可变存储，定期归档 |
| 事件流 | 随数据库备份 / 单独归档 |
| 研究结果 | 版本控制 / 对象存储 |

---

## 3. 恢复流程

```text
Service Failure
      ↓
Infrastructure Recovery
      ↓
Database Recovery
      ↓
Event Replay
      ↓
State Rebuild
      ↓
Reconciliation
      ↓
Consistency Verification
      ↓
Service Resume
```

---

## 4. 核心原则

> **恢复不是简单"把服务重新启动"，而是恢复系统状态的一致性。**

---

## 5. 恢复验证

- 定期恢复演练（从备份恢复并验证）
- 恢复后必须运行 Reconciliation 验证一致性
- 记录恢复过程（审计）

---

## 6. 幂等与重放

- Event Replay 支持确定性重建
- 同一决策 ID / 事件 ID 不重复生效
- 恢复后通过对账确认账实一致

---

## 7. 相关文档

- 数据库：[DATABASE.md](./DATABASE.md)
- 对账引擎：[../02-technical/RECONCILIATION_ENGINE.md](../02-technical/RECONCILIATION_ENGINE.md)
- 事故响应：[INCIDENT_RESPONSE.md](./INCIDENT_RESPONSE.md)
