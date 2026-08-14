# ICYQuant Position Engine

> 本文档描述持仓引擎的职责与持仓模型。

---

## 1. 职责

Position Engine 负责持仓的维护：

```text
Execution → Position Update → Position Snapshot
```

核心能力：

- 开仓 / 加仓 / 减仓 / 平仓
- 成本基准维护（平均成本 / FIFO 等）
- 未实现盈亏（Unrealized PnL）
- 持仓快照与查询

---

## 2. 持仓模型

```text
position_id / account_id / portfolio_id
symbol
quantity（净持仓）
avg_cost（成本基准）
realized_pnl（已实现盈亏）
unrealized_pnl（未实现盈亏）
side（LONG / SHORT）
updated_at
```

---

## 3. 持仓更新流程

```text
Execution Filled
    ↓
PositionUpdateEvent
    ↓
Position Engine 计算新持仓
    ↓
PositionUpdated 事件发布
    ↓
Position Snapshot 持久化
```

---

## 4. 与 Ledger 的关系

- Position 表示"持有多少"
- Ledger 表示"账务如何"
- 二者通过 Reconciliation 对账保持一致

```text
Position ≠ Execution → 检测
Ledger ≠ Position → 检测
```

---

## 5. 核心模块

| 模块 | 职责 |
|------|------|
| `services/position` | 持仓模型与更新 |
| `services/position/model` | 持仓实体 |
| `services/position/repository` | 持仓持久化 |

---

## 6. 相关文档

- 账本引擎：[LEDGER_ENGINE.md](./LEDGER_ENGINE.md)
- 执行引擎：[EXECUTION_ENGINE.md](./EXECUTION_ENGINE.md)
- 对账引擎：[RECONCILIATION_ENGINE.md](./RECONCILIATION_ENGINE.md)
