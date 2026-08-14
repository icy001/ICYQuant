# ICYQuant Product Requirements

> 本文档定义 ICYQuant 的产品目标、核心用户与业务问题域。

---

## 1. 产品目标

ICYQuant 的核心目标**不是追求"策略数量"**，而是建立一个能够承载策略的**稳定交易基础设施**。

系统需要解决以下 13 个核心问题：

| # | 问题 | 对应能力 |
|---|------|----------|
| 1 | 策略如何产生交易信号 | Strategy Engine / Signal Engine |
| 2 | 信号如何经过验证 | Signal Validation / Order Intent Validation |
| 3 | 信号如何进入风险决策 | Risk Decision Context |
| 4 | 风险如何决定是否允许交易 | Risk Decision（APPROVED / REJECTED） |
| 5 | 如何生成订单 | Order Intent → Order |
| 6 | 如何执行订单 | Execution Engine / Broker Adapter |
| 7 | 如何维护 Position | Position Engine |
| 8 | 如何维护 Ledger | Ledger Engine（复式记账） |
| 9 | 如何发现数据不一致 | Reconciliation Comparator |
| 10 | 如何进行自动恢复 | Repair / Recovery / Replay |
| 11 | 如何追踪完整交易链路 | Correlation ID / Audit / Trace |
| 12 | 如何进行确定性 Replay | Event Store / Replay |
| 13 | 如何进行 Research / Factor Analysis | Factor Research Pipeline |

---

## 2. 核心用户

### 2.1 Quant Researcher

负责：

- Factor Research
- Strategy Research
- Backtesting
- Performance Analysis
- Signal Analysis

### 2.2 Strategy Developer

负责：

- Strategy Runtime
- Signal Generation
- Signal Validation
- Strategy Adapter

### 2.3 Trading / Execution

负责：

- Order
- Execution
- Position
- Execution Monitoring

### 2.4 Risk

负责：

- Risk Policy
- Risk Decision
- Exposure
- Limit
- Recovery Request

### 2.5 Platform / Operations

负责：

- Deployment
- Monitoring
- Recovery
- Backup
- Incident Handling

---

## 3. 非功能需求

### 3.1 可靠性

- 幂等性：事件重放 / 重试 / 重启不产生重复结果
- 可恢复性：状态可重建，账实可对平
- 可审计性：任意交易可回答"为什么产生、为什么通过、怎么下单、怎么成交、最终形成什么状态"

### 3.2 安全

- 认证：Authentication
- 授权：Authorization / RBAC（角色与权限分离）
- 审计：Audit（不可变）
- 限流：Rate Limit

### 3.3 可观测

- 结构化日志（JSON + trace_id）
- 指标（Metrics）
- 监控（CPU / Memory / 交易指标 / 风险指标）

### 3.4 可扩展

- 事件驱动：新增 Domain 通过 Event Bus 接入
- Broker Adapter 可插拔
- Plugin / Feature Flag 机制

---

## 4. 产品边界（不做的事）

- 不内置"稳赚策略"
- 不提供经纪商合规牌照
- 不替代实盘券商系统（提供接口而非认证）
- 不承诺实盘盈利

---

## 5. 相关文档

- 产品架构：[PRODUCT_ARCHITECTURE.md](./PRODUCT_ARCHITECTURE.md)
- 用户指南：[USER_GUIDE.md](./USER_GUIDE.md)
- 交易工作流：[TRADING_WORKFLOW.md](./TRADING_WORKFLOW.md)
- 风控规范：[RISK_CONTROL_SPEC.md](./RISK_CONTROL_SPEC.md)
