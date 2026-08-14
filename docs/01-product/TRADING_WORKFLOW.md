# ICYQuant Trading Workflow

> 本文档描述 ICYQuant 的核心业务主链：从行情到账实对账的完整交易流程。

---

## 1. 业务主链

```text
Market Data
     │
     ▼
Research / Strategy
     │
     ▼
Signal Generation
     │
     ▼
Signal Validation
     │
     ▼
Approved Signal
     │
     ▼
Risk Decision
     │
 ┌───┴────┐
 │        │
REJECT   APPROVE
 │        │
 END      ▼
      Order Request
           │
           ▼
      Order Engine
           │
           ▼
    Execution Engine
           │
           ▼
       Execution
           │
           ▼
       Position
           │
           ▼
        Ledger
           │
           ▼
  Reconciliation Engine
```

---

## 2. 阶段详解

### 2.1 信号生成（Signal Generation）

- Strategy Runtime 消费行情，产生信号
- 信号携带策略 ID、方向、数量、价格约束等

### 2.2 信号验证（Signal Validation）

- 验证信号合法性（Symbol、数量、方向、有效性）
- 构造订单意图并验证（`OrderIntentValidator`）

### 2.3 风险决策（Risk Decision）

- 构建决策上下文（`RiskDecisionContext`）
- 评估风险政策（`PolicyEvaluator`）
- 生成决策（`RiskDecision`：APPROVED / REJECTED）
- 生成不可变追踪（`RiskDecisionTrace`）
- 幂等审计（`RiskDecisionAudit`）

### 2.4 订单（Order）

- 订单意图 → 订单
- 订单生命周期状态机（创建 / 提交 / 接受 / 拒绝 / 部分成交 / 完成）
- 幂等准入，防重复下单

### 2.5 执行（Execution）

- 执行引擎驱动成交
- Broker Adapter 可插拔（真实 / 模拟）
- 执行跟踪与成交回报

### 2.6 持仓（Position）

- Position 更新（开仓 / 加仓 / 减仓 / 平仓）
- 成本基准、未实现盈亏

### 2.7 账本（Ledger）

- 复式记账（每笔交易成对记账）
- 事件溯源 + 投影
- 试算平衡

### 2.8 对账（Reconciliation）

- 检测账实不一致
- 分类、调查、修复、验证、关闭

---

## 3. 分支场景

### 3.1 风险拒绝

```text
Signal → Risk Decision → REJECTED → 交易终止（含追踪与审计）
```

### 3.2 订单拒绝

```text
Order → OrderEngine → 校验失败 → 订单拒绝（可审计）
```

### 3.3 事件缺失 / 重复

```text
Reconciliation → Detect（Event Missing / Duplicate）→ Classify → Repair → Verify
```

### 3.4 状态不一致

```text
Ledger ≠ Position
Position ≠ Execution
Execution ≠ Order
→ Reconciliation → Rebuild / Repair → Verify → Close
```

---

## 4. 一致性与幂等保证

- 每笔交易通过 **Correlation ID** 串联全链路
- 每个关键环节支持 **Idempotency**
- 每个状态变更通过 **Event** 驱动
- 每次恢复通过 **Replay / Repair / Verify** 验证

---

## 5. 相关文档

- 产品需求：[PRODUCT_REQUIREMENTS.md](./PRODUCT_REQUIREMENTS.md)
- 风控规范：[RISK_CONTROL_SPEC.md](./RISK_CONTROL_SPEC.md)
- 事件驱动架构：[../02-technical/EVENT_DRIVEN_ARCHITECTURE.md](../02-technical/EVENT_DRIVEN_ARCHITECTURE.md)
- 对账引擎：[../02-technical/RECONCILIATION_ENGINE.md](../02-technical/RECONCILIATION_ENGINE.md)
