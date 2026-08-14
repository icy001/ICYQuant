# ICYQuant Domain Model

> 本文档描述 ICYQuant 的核心领域模型与领域关系。

---

## 1. 核心 Domain

```text
Strategy
Signal
Risk Decision
Order
Execution
Position
Ledger
Reconciliation
Factor
Portfolio
Account
```

---

## 2. 核心领域关系

```text
Strategy
   │
   └── generates
          ↓
        Signal
          │
          └── validated
                 ↓
           Approved Signal
                 │
                 └── evaluated
                        ↓
                  Risk Decision
                        │
                        └── approved
                               ↓
                         Order Request
                               ↓
                             Order
                               ↓
                          Execution
                               ↓
                           Position
                               ↓
                            Ledger
```

---

## 3. 领域对象说明

### 3.1 Strategy

- 策略定义、运行时状态
- 生命周期：Load → Validate → Deploy → Run → Snapshot → Recovery

### 3.2 Signal

- 策略产出的交易信号
- 字段：策略 ID、方向、数量、价格约束、时间戳

### 3.3 Risk Decision

- 风险决策结果（APPROVED / REJECTED）
- 关联 `RiskDecisionTrace`（不可变）
- 关联 `ContextSnapshot`（决策数据快照）

### 3.4 Order

- 订单实体
- 生命周期状态机：创建 → 提交 → 接受 / 拒绝 → 成交 / 完成
- 幂等准入

### 3.5 Execution

- 成交 / 执行记录
- 关联 Broker 回报

### 3.6 Position

- 持仓：数量、成本基准、未实现盈亏

### 3.7 Ledger

- 账本条目（复式记账）
- 事件溯源 + 投影

### 3.8 Reconciliation

- 差异（Difference）、分类、修复计划、生命周期

### 3.9 Factor

- 因子定义、因子值、因子暴露

### 3.10 Portfolio / Account

- 组合与账户维度

---

## 4. 跨领域标识

每笔交易通过 **Correlation ID** 串联：

```text
Strategy
   ↓
Signal ID
   ↓
Risk Decision ID
   ↓
Order ID
   ↓
Execution ID
   ↓
Position ID
   ↓
Ledger Entry
```

> 目标：任意一笔交易，都能回答"为什么产生、为什么通过、怎么下单、怎么成交、最终形成什么持仓和账务状态"。

---

## 5. 领域不变式

| 不变式 | 说明 |
|--------|------|
| Risk 不直接修改交易状态 | 只判断 + 请求恢复 |
| 审计不可变 | 历史决策不重算 |
| 幂等 | 同一决策 ID 只生效一次 |
| 复式记账平衡 | 借贷必相等 |
| 状态显式 | 重要状态均为显式状态机 |

---

## 6. 相关文档

- 系统架构：[SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md)
- 事件驱动架构：[EVENT_DRIVEN_ARCHITECTURE.md](./EVENT_DRIVEN_ARCHITECTURE.md)
- 各引擎文档：STRATEGY / RISK / ORDER / EXECUTION / POSITION / LEDGER / RECONCILIATION
