# ICYQuant System Architecture

> 本文档描述 ICYQuant 的技术架构：模块化、事件驱动、以交易生命周期为主链的系统设计。

---

## 1. 架构总览

ICYQuant 采用**模块化、事件驱动架构**。

```text
                    ┌────────────────────┐
                    │    Market Data     │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │ Strategy Runtime   │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │ Signal Validation  │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │   Risk Decision    │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │   Order Engine     │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │ Execution Engine   │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │ Position Engine    │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │   Ledger Engine    │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │ Reconciliation     │
                    └────────────────────┘
```

---

## 2. 横向基础设施

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

## 3. 代码库结构（services/）

| 目录 | 职责 |
|------|------|
| `services/strategy` | 策略引擎、信号、组合 |
| `services/risk` | 风险决策链（domain / application / rules / audit / service / evaluator / policy） |
| `services/order` | 订单生命周期、OMS |
| `services/execution` | 执行引擎、Broker 适配 |
| `services/position` | 持仓模型 |
| `services/ledger` | 复式记账、事件溯源 |
| `services/reconciliation` | 对账、修复、自愈 |
| `services/control_plane` | 控制网关、事故、告警、审计、授权 |
| `services/event_store` | 事件存储抽象 |
| `services/eventbus` | 事件总线实现 |
| `services/governance` | 治理决策台账、审批、职责分离 |
| `services/attribution` | 绩效归因 |
| `services/risk_intelligence` | 风险智能 |

---

## 4. 应用层（apps/）

| 应用 | 说明 |
|------|------|
| `apps/api` | FastAPI 网关，REST 入口（v1 分组） |
| `apps/worker` | 事件消费者、后台任务 |

---

## 5. 基础设施层

| 组件 | 用途 |
|------|------|
| PostgreSQL 16+ | 主数据库（业务 + 事件存储） |
| Redis 7+ | 缓存、限流、锁 |
| Kafka 3.8+ | 事件总线 |
| alembic | 数据库迁移 |
| Docker / Compose | 部署（见 03-operations） |

---

## 6. 关键架构决策

| 决策 | 理由 |
|------|------|
| 事件驱动 | 域间解耦、可重放、可审计 |
| 显式状态机 | 交易状态可解释、可恢复 |
| 幂等写入 | 重试 / 重放安全 |
| Risk 只判断不修改 | 最小化系统写权限 |
| Reconciliation 负责修复 | 自愈闭环 |
| 不可变审计 | 历史可追溯、防篡改 |

---

## 7. 相关文档

- 领域模型：[DOMAIN_MODEL.md](./DOMAIN_MODEL.md)
- 事件驱动架构：[EVENT_DRIVEN_ARCHITECTURE.md](./EVENT_DRIVEN_ARCHITECTURE.md)
- 部署：[../03-operations/DEPLOYMENT.md](../03-operations/DEPLOYMENT.md)
- 数据架构：[DATA_ARCHITECTURE.md](./DATA_ARCHITECTURE.md)
