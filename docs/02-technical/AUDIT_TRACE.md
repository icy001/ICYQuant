# ICYQuant Audit & Trace

> 本文档描述 ICYQuant 的审计与追踪能力。

---

## 1. 目标

系统中的重要操作必须具备**可追踪能力**。

核心 Trace：

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

通过 **Correlation ID** 可以把整个交易生命周期串起来。

> 目标：任意一笔交易，都能够回答"为什么产生、为什么通过、怎么下单、怎么成交、最终形成什么持仓和账务状态"。

---

## 2. 审计原则

| 原则 | 说明 |
|------|------|
| 不可变 | 审计记录不可随意修改 |
| 幂等 | 同一标识不产生重复审计 |
| 只记录不重算 | Audit 不重新计算业务结果 |
| 全链路 | 从策略到账本全程可追溯 |

---

## 3. 风险决策审计

`RiskDecisionAudit`：

- 只记录已产生的最终决策
- 按 `decision_id` 幂等写入
- 保留完整 `RiskDecisionTrace`

---

## 4. 审计维度

| 类型 | 说明 |
|------|------|
| 交易审计 | 订单 / 执行 / 成交 |
| 风险审计 | 风险决策与追踪 |
| 安全审计 | 登录 / 授权 / 敏感操作 |
| 治理审计 | 审批 / 决策台账 |
| 运维审计 | 配置变更 / 部署 / 恢复 |

---

## 5. 实现组件

| 组件 | 路径 | 职责 |
|------|------|------|
| `RiskDecisionTrace` | `services/risk/domain/` | 决策追踪（不可变） |
| `RiskDecisionAudit` | `services/risk/audit/` | 决策审计（幂等） |
| `control_plane/audit*` | `services/control_plane/` | 平台审计事件 |
| Event Store | `services/event_store` | 事件持久化 |

---

## 6. 审计生命周期

```text
操作发生
    ↓
生成审计事件
    ↓
持久化（幂等）
    ↓
可查询 / 可导出
    ↓
防篡改（不可变）
```

---

## 7. 相关文档

- 事件驱动架构：[EVENT_DRIVEN_ARCHITECTURE.md](./EVENT_DRIVEN_ARCHITECTURE.md)
- 风控引擎：[RISK_ENGINE.md](./RISK_ENGINE.md)
- 审计策略：[../04-security/AUDIT_POLICY.md](../04-security/AUDIT_POLICY.md)
