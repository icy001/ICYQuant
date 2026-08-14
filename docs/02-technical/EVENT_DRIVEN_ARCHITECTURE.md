# ICYQuant Event-Driven Architecture

> 本文档描述 ICYQuant 的事件驱动架构：事件模型、事件总线、以及事件如何支撑 Replay / Audit / Recovery。

---

## 1. 事件驱动原则

ICYQuant 使用 **Event Bus** 连接核心 Domain。每个领域的状态变更通过事件发布，其他领域通过订阅事件响应。

```text
Cause
 ↓
Event
 ↓
State
 ↓
Next Event
```

---

## 2. 典型事件

```text
SignalGenerated
SignalApproved
RiskDecisionCreated
RiskApproved
RiskRejected
OrderCreated
OrderSubmitted
OrderAccepted
OrderRejected
ExecutionCreated
PositionUpdated
LedgerUpdated
ReconciliationDetected
RecoveryRequested
RecoveryCompleted
```

---

## 3. 事件结构

每个事件包含：

```text
Event ID
Aggregate ID
Event Type
Timestamp
Version
Payload
Correlation ID
Causation ID
```

### 3.1 Correlation ID

- 串联整个交易生命周期（Strategy → Signal → Risk → Order → Execution → Position → Ledger）
- 审计与排查的锚点

### 3.2 Causation ID

- 记录触发本事件的父事件
- 建立事件因果链，支撑确定性 Replay

---

## 4. 事件总线实现

| 组件 | 说明 |
|------|------|
| `services/eventbus` | 事件总线实现（发布 / 订阅 / 投递） |
| `services/event_store` | 事件存储抽象（持久化、按聚合读取） |
| 后端 | Kafka 3.8+（生产）/ In-memory（测试） |

---

## 5. 事件溯源与投影

### 5.1 事件溯源（Event Sourcing）

- Ledger 等核心状态以事件流为唯一事实源
- 状态可通过事件重放重建

### 5.2 投影（Projection）

- 从事件流投影出查询模型（Position / Ledger 视图）

---

## 6. Replay 与一致性

```text
Event Stream
    ↓
Replay
    ↓
State Rebuild
    ↓
Reconciliation
    ↓
Consistency Verification
```

- 相同输入 → 可解释、可重复结果（Deterministic Replay）
- 事件缺失 / 重复可通过对账检测

---

## 7. 幂等性

- 事件消费者按事件 ID / 决策 ID 幂等
- 重试、重放、重启均不产生重复副作用

---

## 8. 相关文档

- 系统架构：[SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md)
- 数据架构：[DATA_ARCHITECTURE.md](./DATA_ARCHITECTURE.md)
- 审计与追踪：[AUDIT_TRACE.md](./AUDIT_TRACE.md)
- 对账引擎：[RECONCILIATION_ENGINE.md](./RECONCILIATION_ENGINE.md)
