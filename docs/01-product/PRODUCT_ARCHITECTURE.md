# ICYQuant Product Architecture

> 本文档从**产品/业务视角**描述 ICYQuant 的整体架构，与技术架构互补。

---

## 1. 业务架构总览

```text
Research
   ↓
Strategy
   ↓
Signal
   ↓
Risk Decision
   ↓
Order
   ↓
Execution
   ↓
Position
   ↓
Ledger
   ↓
Reconciliation
```

这条链路是 ICYQuant 最重要的**业务主链**。

---

## 2. 业务域划分

| 域 | 职责 | 不负责 |
|----|------|--------|
| Research | 因子、策略、回测、归因 | 交易执行 |
| Strategy | 策略运行、信号生成 | 订单执行 |
| Signal | 信号验证、意图验证 | 风险判断 |
| Risk | 判断、分类、决策、追踪、恢复请求 | 直接修改交易状态 |
| Order | 订单生命周期、OMS | 成交撮合 |
| Execution | 执行、Broker 适配、跟踪 | 记账 |
| Position | 持仓、成本、盈亏 | 账务 |
| Ledger | 复式记账、事件溯源 | 状态修复 |
| Reconciliation | 检测、分类、修复、验证 | 风险判断 |
| Control Plane | 控制网关、事故、告警、审计 | 业务交易 |

---

## 3. 横向能力层

```text
┌───────────────────────────────────────────────────┐
│ Event Bus                                          │
│ Audit / Trace                                      │
│ Persistence                                        │
│ Authentication / RBAC                              │
│ Rate Limiting                                      │
│ Monitoring                                         │
│ Logging                                            │
│ Replay                                             │
└───────────────────────────────────────────────────┘
```

---

## 4. 产品模块清单（GA 核心）

| 模块 | 说明 |
|------|------|
| Research | 研究流程、因子、信号 |
| AI | AI 平台（agents / automl / mlops 等） |
| Backtest | 回测引擎 |
| OMS | 订单管理系统 |
| EMS | 执行管理系统 |
| Risk | 风险决策链 |
| Portfolio | 组合与资金分配 |
| Lakehouse | 数据湖仓 |
| Observability | 可观测性 |
| Security | 安全与权限 |
| Platform | 平台基础设施 |
| Control Plane | 控制平面（事故、告警、治理） |

---

## 5. 用户界面层

- **API Service**：FastAPI 网关（apps/api），REST 入口
- **Admin / UI**：管理界面（可扩展）
- **Worker**：事件消费者与后台任务（apps/worker）

---

## 6. 相关文档

- 产品需求：[PRODUCT_REQUIREMENTS.md](./PRODUCT_REQUIREMENTS.md)
- 系统架构：[../02-technical/SYSTEM_ARCHITECTURE.md](../02-technical/SYSTEM_ARCHITECTURE.md)
- 领域模型：[../02-technical/DOMAIN_MODEL.md](../02-technical/DOMAIN_MODEL.md)
