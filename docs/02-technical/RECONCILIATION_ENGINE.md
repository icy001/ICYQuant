# ICYQuant Reconciliation Engine

> 本文档描述对账引擎（系统自愈核心）的设计。

---

## 1. 职责

Reconciliation Engine 是 ICYQuant 的**系统自愈核心**。

它主要解决：

```text
Ledger ≠ Position
Position ≠ Execution
Execution ≠ Order
Event Missing
Event Duplicate
State Corruption
```

---

## 2. 核心流程

```text
Detect
  ↓
Classify
  ↓
Investigate
  ↓
Rebuild / Repair
  ↓
Verify
  ↓
Close
```

| 阶段 | 说明 |
|------|------|
| Detect | 检测数据不一致 |
| Classify | 分类（类型、严重度） |
| Investigate | 调查根因 |
| Rebuild / Repair | 重建状态 / 修复数据 |
| Verify | 验证一致性恢复 |
| Close | 关闭生命周期（含审计） |

---

## 3. 支持能力

- State Rebuild（状态重建）
- Event Replay（事件重放）
- Data Repair（数据修复）
- Consistency Check（一致性检查）
- Recovery（恢复）
- Idempotency（幂等）

---

## 4. 自愈闭环

```text
交易系统
    ↓
发现异常
    ↓
Risk Decision
    ↓
Recovery Request
    ↓
Reconciliation
    ↓
Repair
    ↓
Verification
```

> 原则：**Risk 负责判断，Reconciliation 负责修复。**

---

## 5. 核心组件

| 组件 | 路径 | 职责 |
|------|------|------|
| `Comparator` | `services/reconciliation/comparator.py` | 差异检测与比较 |
| `Difference` | `services/reconciliation/models/difference.py` | 差异模型 |
| `Service` | `services/reconciliation/service.py` | 对账服务主流程 |
| 修复执行 | `services/reconciliation/` | 修复 / 重建 / 重放 |

---

## 6. 差异分类

```text
POSITION_MISMATCH（持仓不一致）
LEDGER_MISMATCH（账务不一致）
EXECUTION_MISMATCH（成交不一致）
EVENT_MISSING（事件缺失）
EVENT_DUPLICATE（事件重复）
STATE_CORRUPTION（状态损坏）
```

---

## 7. 相关文档

- 风控引擎：[RISK_ENGINE.md](./RISK_ENGINE.md)
- 账本引擎：[LEDGER_ENGINE.md](./LEDGER_ENGINE.md)
- 事件驱动架构：[EVENT_DRIVEN_ARCHITECTURE.md](./EVENT_DRIVEN_ARCHITECTURE.md)
- 备份与恢复：[../03-operations/BACKUP_RECOVERY.md](../03-operations/BACKUP_RECOVERY.md)
