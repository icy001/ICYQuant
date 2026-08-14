# ICYQuant Project Scope

> 本文档定义 ICYQuant 的项目边界：做什么、不做什么、已建成什么、未建成什么。

---

## 1. In Scope（范围内）

### 1.1 核心交易生命周期

| # | 能力 | 状态 |
|---|------|------|
| 1 | 策略如何产生交易信号 | ✅ 已建成（Strategy Engine / Signal Engine） |
| 2 | 信号如何经过验证 | ✅ 已建成（Signal Validation / OrderIntentValidator） |
| 3 | 信号如何进入风险决策 | ✅ 已建成（RiskDecisionContext → PolicyEvaluator） |
| 4 | 风险如何决定是否允许交易 | ✅ 已建成（APPROVED / REJECTED 决策链） |
| 5 | 如何生成订单 | ✅ 已建成（OrderIntent → Order） |
| 6 | 如何执行订单 | ✅ 已建成（Execution Engine / Broker Adapter） |
| 7 | 如何维护 Position | ✅ 已建成（Position Model / Cost Basis / PnL） |
| 8 | 如何维护 Ledger | ✅ 已建成（复式记账 / 事件溯源 / 投影） |
| 9 | 如何发现数据不一致 | ✅ 已建成（Reconciliation Comparator） |
| 10 | 如何进行自动恢复 | ✅ 已建成（Repair / Recovery / Replay） |
| 11 | 如何追踪完整交易链路 | ✅ 已建成（Correlation ID / Audit / Trace） |
| 12 | 如何进行确定性 Replay | ✅ 已建成（Event Store / Replay / Comparator） |
| 13 | 如何进行 Research / Factor Analysis | ✅ 已建成（Alpha / Factor / Attribution） |

### 1.2 横向基础设施

| 能力 | 状态 |
|------|------|
| Event Bus | ✅ |
| Audit / Trace | ✅ |
| Persistence（PostgreSQL / SQLite / Memory） | ✅ |
| Replay | ✅ |
| Recovery | ✅ |
| Monitoring | ✅ |
| Logging（结构化 JSON + trace_id） | ✅ |
| RBAC | ✅ |
| Rate Limit | ✅ |
| Control Plane（控制网关 / 事故管理 / 告警） | ✅ |
| Governance（四眼审批 / 职责分离 / 决策台账） | ✅ |
| Feature Flags / Plugin / Service Discovery | ✅ |

---

## 2. Out of Scope（范围外）

当前版本**不包含 / 不承诺**：

- **实盘盈利能力**：ICYQuant 不是"装上就能赚钱"的系统，是交易基础设施。
- **经纪商官方认证**：Broker Adapter 为可扩展接口，未内置任何实盘经纪商认证。
- **合规监管牌照**：系统提供审计能力，不替代持牌机构的合规责任。
- **策略库**：系统承载策略，但不内置可盈利策略集。
- **Kubernetes 生产运维**：提供 Helm Chart，但默认推荐 Docker Compose 起步。

---

## 3. 明确的技术边界

### 3.1 Risk 模块边界

Risk 引擎**不直接修改交易状态**，它只负责：

```text
Evaluate → Classify → Decide → Trace → Request Recovery
```

而不是：

```text
直接修改 Position / 直接修改 Ledger / 直接修改 Order
```

> **Risk 负责判断，Reconciliation 负责修复。**

### 3.2 Reconciliation 边界

Reconciliation 负责：

```text
Detect → Classify → Investigate → Rebuild/Repair → Verify → Close
```

支持 State Rebuild、Event Replay、Data Repair、Consistency Check、Recovery、Idempotency。

### 3.3 审计边界

- Decision 不负责 Audit；Audit 不修改 Decision。
- Audit 只记录已产生的最终决策，**不重新计算 Risk**。
- 按 `decision_id` 幂等写入。

---

## 4. 用户角色范围

| 角色 | 职责 |
|------|------|
| Quant Researcher | Factor / Strategy / Backtest / Performance / Signal 分析 |
| Strategy Developer | Strategy Runtime / Signal / Validation / Adapter |
| Trading / Execution | Order / Execution / Position / 执行监控 |
| Risk | 风险政策 / 决策 / 敞口 / 限额 / 恢复请求 |
| Platform / Operations | 部署 / 监控 / 恢复 / 备份 / 事故处理 |

---

## 5. 相关文档

- 项目总览：[PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md)
- 项目状态：[PROJECT_STATUS.md](./PROJECT_STATUS.md)
- 项目路线图：[PROJECT_ROADMAP.md](./PROJECT_ROADMAP.md)
