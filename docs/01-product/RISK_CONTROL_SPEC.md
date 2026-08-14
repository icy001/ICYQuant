# ICYQuant Risk Control Specification

> 本文档是 ICYQuant **风控规范**：定义风险控制的边界、决策链、追踪与恢复机制。这是 Commit 39~41 最重要的成果之一。

---

## 1. 核心原则

**Risk Engine 不直接修改交易状态。**

它负责：

```text
Evaluate
Classify
Decide
Trace
Request Recovery
```

而不是：

```text
直接修改 Position
直接修改 Ledger
直接修改 Order
```

> **Risk 负责判断，Reconciliation 负责修复。**
> 这样可以避免风险模块拥有过大的系统写权限。

---

## 2. 风险决策链

最终形成：

```text
Risk
 │
 ├── Detect
 ├── Evaluate
 ├── Classify
 ├── Decide
 ├── Persist
 ├── Audit
 ├── Replay
 └── Recovery Request
              │
              ▼
       Reconciliation
              │
              └── Repair
```

---

## 3. 决策生命周期

```text
Context → Rule Evaluation → Decision → Execution Gate → Trace → Audit
```

### 3.1 决策上下文（Context）

- 捕获决策时的数据快照（`ContextSnapshot`）：仓位、敞口、限额、行情等
- 快照保证历史决策可解释

### 3.2 规则评估（Rule Evaluation）

- `PolicyEvaluator` 逐条评估风险政策
- 记录所有评估过的规则与触发的规则

### 3.3 决策（Decision）

- 生成 `RiskDecision`：APPROVED / REJECTED
- 附带触发原因与规则

### 3.4 执行门控（Execution Gate）

- 决策结果作为订单/执行入口的控制点
- APPROVED → 放行；REJECTED → 拦截

### 3.5 追踪（Trace）

- `RiskDecisionTrace`（frozen，不可变）
- 8 个字段：`decision_id / request_id / strategy_id / decision / evaluated_rules / triggered_rules / context_snapshot / created_at`
- **一次决策必须能回答"为什么通过 / 为什么拒绝 / 依据什么数据"**

### 3.6 审计（Audit）

- `RiskDecisionAudit`：只记录已产生的最终决策，**不重新计算 Risk**
- 按 `decision_id` 幂等写入
- 历史决策不因环境变化而重算

---

## 4. 幂等与重放保证

| 场景 | 保证 |
|------|------|
| Event Retry | 不产生重复审计 |
| Consumer Retry | 不产生重复审计 |
| Restart | 不产生重复审计 |
| Replay | 不产生重复审计 |

实现：以 `decision_id` 为主键，配合锁与 setdefault 语义。

---

## 5. 风险决策 Service 收口流程

```text
context_builder.build
    ↓
rule_engine.evaluate
    ↓
decision_builder.build
    ↓
trace_builder.build
    ↓
audit.record
    ↓
return decision
```

---

## 6. 恢复请求（Recovery Request）

- Risk 决策后，如发现异常可发出 Recovery Request
- Reconciliation 接收后执行修复
- 修复完成后再验证一致性

---

## 7. 风控监控指标

- Exposure（敞口）
- Drawdown（回撤）
- Risk Decision 数量 / 拒绝率
- Recovery Request 数量
- Reconciliation Exception 数量

---

## 8. 相关文档

- 技术风控引擎：[../02-technical/RISK_ENGINE.md](../02-technical/RISK_ENGINE.md)
- 对账引擎：[../02-technical/RECONCILIATION_ENGINE.md](../02-technical/RECONCILIATION_ENGINE.md)
- 审计与追踪：[../02-technical/AUDIT_TRACE.md](../02-technical/AUDIT_TRACE.md)
