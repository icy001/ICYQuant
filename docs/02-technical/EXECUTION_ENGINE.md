# ICYQuant Execution Engine

> 本文档描述执行引擎（EMS）的职责：订单执行、Broker 适配、执行跟踪。

---

## 1. 职责

Execution Engine 负责：

```text
Order → Execution Gateway → Broker → Execution Result
```

核心能力：

- 订单提交到执行端
- Broker Adapter 可插拔（真实 / 模拟）
- 执行回报处理（成交、拒绝、部分成交）
- 执行跟踪与质量监控

---

## 2. 组件结构

| 组件 | 说明 |
|------|------|
| Execution Gateway | 执行统一入口 |
| Broker Adapter | 适配不同 Broker（接口化） |
| Simulator | 模拟执行（测试 / Paper Trading） |
| Execution Tracker | 跟踪执行状态 |

---

## 3. 执行流程

```text
Order Engine
    ↓
Execution Request
    ↓
Execution Gateway
    ↓
Broker Adapter（真实 / 模拟）
    ↓
Execution Result（成交 / 拒绝 / 部分成交）
    ↓
回写 Order / Position / Ledger 事件
```

---

## 4. 执行事件

```text
ExecutionCreated
ExecutionFilled
ExecutionPartialFill
ExecutionRejected
```

---

## 5. 与 Position / Ledger 衔接

- 成交事件 → `PositionUpdated`（持仓更新）
- 成交事件 → `LedgerUpdated`（记账）

---

## 6. 执行监控指标

- Execution Count（成交笔数）
- Fill Rate（成交率）
- Reject Rate（拒绝率）
- 滑点 / 执行质量

---

## 7. 核心模块

| 模块 | 职责 |
|------|------|
| `services/execution` | 执行引擎 |
| `services/execution/adapters` | Broker 适配器 |
| `services/execution/gateway` | 执行网关 |

---

## 8. 相关文档

- 订单引擎：[ORDER_ENGINE.md](./ORDER_ENGINE.md)
- 持仓引擎：[POSITION_ENGINE.md](./POSITION_ENGINE.md)
- 账本引擎：[LEDGER_ENGINE.md](./LEDGER_ENGINE.md)
