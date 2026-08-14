# ICYQuant Ledger Engine

> 本文档描述账本引擎的设计：复式记账、事件溯源与投影。

---

## 1. 职责

Ledger Engine 负责账务记录：

- 复式记账（每笔交易成对记账：借贷必相等）
- 事件溯源（事件流为唯一事实源）
- 投影（从事件流投影查询视图）
- 试算平衡（Trial Balance）

---

## 2. 记账模型

```text
ledger_entry_id
account（科目）
side（DEBIT / CREDIT）
amount
currency
trade / execution reference
correlation_id
booked_at
```

**不变式**：借贷必相等。

---

## 3. 事件溯源架构

```text
Trade Events（原始事实）
    ↓
Event Store（持久化事件流）
    ↓
Projection
    ↓
Ledger View（账务视图）
```

- 事件流可重放，账务状态可重建
- 投影失败可从事件流恢复

---

## 4. 记账流程

```text
Execution Filled
    ↓
LedgerEvent（原始事件）
    ↓
Ledger Bookkeeping（复式记账）
    ↓
LedgerEntry × 2（借贷成对）
    ↓
LedgerUpdated 事件
    ↓
Projection → Ledger View
```

---

## 5. 一致性保证

- 试算平衡校验：所有 DEBIT 之和 == 所有 CREDIT 之和
- 与 Position 对账：`Ledger ≠ Position → Reconciliation 检测`
- 事件缺失 / 重复通过对账与重放检测

---

## 6. 核心模块

| 模块 | 职责 |
|------|------|
| `services/ledger` | 账本引擎 |
| `services/ledger/events` | 记账事件 |
| `services/ledger/projection` | 投影 |
| `services/ledger/event_store` | 事件存储接入 |

---

## 7. 相关文档

- 持仓引擎：[POSITION_ENGINE.md](./POSITION_ENGINE.md)
- 对账引擎：[RECONCILIATION_ENGINE.md](./RECONCILIATION_ENGINE.md)
- 事件驱动架构：[EVENT_DRIVEN_ARCHITECTURE.md](./EVENT_DRIVEN_ARCHITECTURE.md)
- 数据架构：[DATA_ARCHITECTURE.md](./DATA_ARCHITECTURE.md)
