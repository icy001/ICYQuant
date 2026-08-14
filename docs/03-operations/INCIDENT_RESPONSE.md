# ICYQuant Incident Response

> 本文档描述 ICYQuant 的生产事故响应流程。

---

## 1. 响应流程

生产异常统一按照：

```text
Detect
 ↓
Classify
 ↓
Contain
 ↓
Investigate
 ↓
Recover
 ↓
Verify
 ↓
Postmortem
```

---

## 2. 严重事件

```text
Order State Inconsistency
Position Inconsistency
Ledger Inconsistency
Event Loss
Duplicate Event
Risk Engine Failure
Execution Failure
Database Failure
```

---

## 3. 优先级原则

> **交易状态不一致 > 普通 API 异常**

交易状态不一致应拥有更高优先级。

---

## 4. 处理指引

### 4.1 Detect（检测）

- 监控告警触发
- Reconciliation 检测到差异
- 用户报告

### 4.2 Classify（分类）

- 确定类型（订单 / 持仓 / 账本 / 事件 / 风控 / 执行 / 数据库）
- 确定严重度

### 4.3 Contain（遏制）

- 使用控制网关：ALLOW / REDUCE_ONLY / BLOCK
- 停止受影响业务（fail-closed）

### 4.4 Investigate（调查）

- 通过 correlation_id / trace_id 追踪全链路
- 检查事件流与审计记录

### 4.5 Recover（恢复）

- 修复数据 / 重建状态 / 重放事件
- 必要时恢复备份

### 4.6 Verify（验证）

- 运行 Reconciliation 验证一致性
- 确认业务恢复

### 4.7 Postmortem（复盘）

- 根因分析
- 改进项（监控 / 流程 / 代码）

---

## 5. 角色分工

| 角色 | 职责 |
|------|------|
| On-call | 第一响应，遏制与调查 |
| 交易域负责人 | 交易状态修复 |
| 风控 | 风险判断与恢复请求 |
| 平台 | 基础设施恢复 |

---

## 6. 相关文档

- 监控：[MONITORING.md](./MONITORING.md)
- 生产运行手册：[PRODUCTION_RUNBOOK.md](./PRODUCTION_RUNBOOK.md)
- 备份恢复：[BACKUP_RECOVERY.md](./BACKUP_RECOVERY.md)
