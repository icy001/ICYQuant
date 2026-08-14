# ICYQuant Audit Policy

> 本文档定义 ICYQuant 的审计策略。

---

## 1. 审计目标

> 任意一笔交易，都能够回答"为什么产生、为什么通过、怎么下单、怎么成交、最终形成什么持仓和账务状态"。

---

## 2. 审计原则

| 原则 | 说明 |
|------|------|
| 不可变 | 审计记录不可随意修改 |
| 幂等 | 同一标识不产生重复审计 |
| 只记录不重算 | Audit 不重新计算业务结果 |
| 全链路 | Strategy → Signal → Risk → Order → Execution → Position → Ledger |

---

## 3. 审计范围

| 类型 | 内容 |
|------|------|
| 交易审计 | 订单 / 执行 / 成交 |
| 风险审计 | 风险决策与追踪（RiskDecisionTrace） |
| 安全审计 | 登录 / 授权 / 敏感操作 |
| 治理审计 | 审批 / 决策台账 / 职责分离 |
| 运维审计 | 配置变更 / 部署 / 恢复 / 控制网关切换 |

---

## 4. 关键审计点

```text
RiskDecisionCreated
OrderCreated
OrderRejected
ExecutionCreated
RecoveryRequested
ControlGatewayChange
ApprovalGranted
```

---

## 5. 审计保留

- 审计记录需满足合规保留期
- 定期归档，不可删除
- 备份策略纳入审计日志

---

## 6. 审计实现

- `RiskDecisionAudit`：按 `decision_id` 幂等写入，只记录不重算
- `control_plane/audit*`：平台审计事件
- Event Store：事件持久化支撑全链路追踪

---

## 7. 相关文档

- 审计与追踪：[../02-technical/AUDIT_TRACE.md](../02-technical/AUDIT_TRACE.md)
- 安全架构：[SECURITY_ARCHITECTURE.md](./SECURITY_ARCHITECTURE.md)
- 安全检查清单：[SECURITY_CHECKLIST.md](./SECURITY_CHECKLIST.md)
