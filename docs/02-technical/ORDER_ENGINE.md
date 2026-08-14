# ICYQuant Order Engine

> 本文档描述订单引擎（OMS）的职责与订单生命周期。

---

## 1. 职责

Order Engine 负责订单的完整生命周期管理：

```text
Order Intent → Order → Submit → Accept/Reject → Fill → Done
```

核心能力：

- 订单创建与准入校验
- 订单生命周期状态机
- 幂等准入（防重复下单）
- 订单路由到执行引擎

---

## 2. 订单生命周期

```text
CREATED
   ↓
SUBMITTED
   ↓
ACCEPTED ←───────────┐
   ↓                 │
PARTIALLY_FILLED ────┤
   ↓                 │
FILLED / DONE        │
                      │
REJECTED ─────────────┘
```

| 状态 | 说明 |
|------|------|
| CREATED | 订单已创建（未提交） |
| SUBMITTED | 已提交执行 |
| ACCEPTED | 交易所/执行端接受 |
| REJECTED | 被拒绝（含原因） |
| PARTIALLY_FILLED | 部分成交 |
| FILLED | 全部成交 |
| DONE | 终态 |

---

## 3. 幂等准入

- 以订单意图 ID / 客户端请求 ID 幂等
- 重复提交不产生重复订单

---

## 4. 订单模型

核心字段：

```text
order_id / client_order_id
strategy_id
symbol
side（BUY / SELL）
quantity
price / order_type
status（生命周期状态）
correlation_id
created_at / updated_at
```

---

## 5. 与风险决策衔接

```text
Risk Decision（APPROVED）
    ↓
Order Request
    ↓
Order Engine
```

**Execution Gate 原则**：风险决策 REJECTED 时，订单引擎不应接受对应请求。

---

## 6. 核心模块

| 模块 | 职责 |
|------|------|
| `services/order` | 订单生命周期、OMS |
| `services/order/state` | 状态机定义 |
| `services/order/repository` | 订单持久化 |

---

## 7. 相关文档

- 执行引擎：[EXECUTION_ENGINE.md](./EXECUTION_ENGINE.md)
- 风控引擎：[RISK_ENGINE.md](./RISK_ENGINE.md)
- 领域模型：[DOMAIN_MODEL.md](./DOMAIN_MODEL.md)
