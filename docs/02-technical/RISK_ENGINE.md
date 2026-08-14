# ICYQuant Risk Engine

> 本文档描述风险引擎的技术设计：决策链、追踪、审计与恢复请求。这是 Commit 39~41 的核心成果。

---

## 1. 职责边界

Risk Engine **不直接修改交易状态**。

它负责：

```text
Evaluate
Classify
Decide
Trace
Request Recovery
```

不负责：

```text
直接修改 Position / Ledger / Order
```

> **Risk 负责判断，Reconciliation 负责修复。**

---

## 2. 决策链（收口流程）

```text
Context → Rule Evaluation → Decision → Execution Gate → Trace → Audit
```

`RiskDecisionService.evaluate` 的完整流程：

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

## 3. 核心组件

| 组件 | 路径 | 职责 |
|------|------|------|
| `RiskDecisionService` | `services/risk/service/risk_decision_service.py` | 决策链收口入口 |
| `RiskDecision` | `services/risk/decision/` | 决策结果（APPROVED / REJECTED） |
| `RiskDecisionTrace` | `services/risk/domain/risk_decision_trace.py` | 不可变追踪 |
| `RiskDecisionAudit` | `services/risk/audit/risk_decision_audit.py` | 幂等审计 |
| `RiskDecisionTraceBuilder` | `services/risk/application/` | Trace 构建 |
| `ContextSnapshot` | `services/risk/` | 决策数据快照 |
| `PolicyEvaluator` | `services/risk/evaluator/` | 政策评估 |
| `PolicyTrace` | `services/risk/` | 政策执行痕迹 |

---

## 4. RiskDecisionTrace（不可变）

```python
@dataclass(frozen=True)
class RiskDecisionTrace:
    decision_id: str
    request_id: str
    strategy_id: str
    decision: RiskDecision
    evaluated_rules: tuple[str, ...]
    triggered_rules: tuple[str, ...]
    context_snapshot: dict
    created_at: datetime
```

- frozen dataclass：字段不可变
- 保留 `evaluated_rules` 与 `triggered_rules`
- 保留 `context_snapshot`（依据什么数据）
- 历史决策不因环境变化而重算

> **一次决策必须能回答"为什么通过 / 为什么拒绝 / 依据什么数据"。**

---

## 5. RiskDecisionAudit（幂等）

- 只记录已产生的最终决策，**不重新计算 Risk**
- 以 `decision_id` 为主键幂等写入
- 并发保护（锁 + setdefault 语义）
- Event Retry / Consumer Retry / Restart / Replay 均不产生重复审计

---

## 6. 边界保证

| 原则 | 实现 |
|------|------|
| Decision 不负责 Audit | 决策构建与审计分离 |
| Audit 不修改 Decision | 审计只读决策结果 |
| 决策 == 审计 == Trace | 三层共享同一决策结果与时间线 |
| 不可变性 | frozen dataclass + 不重算 |

---

## 7. 恢复请求

```text
Risk
 └── Recovery Request
        ↓
Reconciliation
        ↓
Repair
```

Risk 判断出异常时发出恢复请求，由 Reconciliation 执行修复。

---

## 8. 风险监控

- Exposure、Drawdown、Risk Decision、Recovery Request、Reconciliation Exception

---

## 9. 相关文档

- 风控规范：[../01-product/RISK_CONTROL_SPEC.md](../01-product/RISK_CONTROL_SPEC.md)
- 审计与追踪：[AUDIT_TRACE.md](./AUDIT_TRACE.md)
- 对账引擎：[RECONCILIATION_ENGINE.md](./RECONCILIATION_ENGINE.md)
