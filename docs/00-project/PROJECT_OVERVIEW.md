# ICYQuant Project Overview

| Attribute | Value |
|-----------|-------|
| **Project** | ICYQuant |
| **Version** | `v0.4.0-alpha2` |
| **Status** | Project Phase Concluded（项目阶段收口） |
| **Latest Commit** | `Commit 41` |
| **Project Type** | Quantitative Trading & Research Platform |
| **License** | MIT |
| **Documentation Freeze** | 是 |

---

## 1. 项目定位

ICYQuant 是一个面向**量化交易研究、策略执行、风险控制、订单管理、执行管理、持仓管理、账本管理以及系统自愈能力建设**的量化交易基础平台。

它**不是**单纯的：

- 回测框架
- 策略脚本集合
- Trading Bot
- Broker API Wrapper

而是按照接近**机构级交易系统**的方式，建立完整交易生命周期：

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

并通过横向基础设施形成闭环：

```text
Event Bus
Audit
Persistence
Replay
Recovery
Monitoring
RBAC
Rate Limit
```

---

## 2. 核心设计原则

### 2.1 Domain First

先定义业务语义，再实现代码。每个 Domain（Strategy / Signal / Risk / Order / Execution / Position / Ledger / Reconciliation）拥有独立、明确的边界。

### 2.2 Explicit State

重要状态必须显式建模。例如 Order 生命周期、Position 状态、Risk Decision 状态、Reconciliation 生命周期均有显式状态机。

### 2.3 Idempotency

交易系统操作必须尽量保证幂等。事件重放、Consumer 重试、重启恢复均不产生重复结果。

### 2.4 Immutable Audit

审计记录不可随意修改。历史 Decision 不因环境变化而重算。

### 2.5 Deterministic Replay

相同输入必须得到可解释、可重复的结果。Replay 是恢复与验证的基础。

### 2.6 Risk 判断，Reconciliation 修复

Risk 模块不直接修改交易状态，只负责判断与请求恢复；Reconciliation 负责修复。**边界避免风险模块拥有过大的系统写权限。**

---

## 3. 覆盖范围

| 领域 | 覆盖内容 |
|------|----------|
| Strategy | 策略引擎、信号生成、信号验证、订单意图、组合决策、资金分配 |
| Risk | 风险决策链、政策评估、限额管理、压力测试、恢复请求 |
| Order | 订单生命周期状态机、OMS、订单路由、幂等准入 |
| Execution | 执行引擎、Broker 适配、执行模拟、跟踪 |
| Position | 持仓模型、成本基准、未实现盈亏 |
| Ledger | 复式记账、事件溯源、投影、试算平衡 |
| Reconciliation | 差异检测、分类、修复、验证、自愈生命周期 |
| Control Plane | 控制网关、事故管理、告警、授权、审计 |
| Governance | 治理决策台账、四眼审批、职责分离、政策评估 |
| Research | 因子研究、信号研究、归因分析 |

---

## 4. 交付形态

- `services/` — 315 个 Python 模块，覆盖全部业务域
- `apps/` — FastAPI 网关与 Worker 应用
- `tests/` — 242 个测试文件（数千个用例）
- `docs/` — 完整文档冻结体系（本文档集）
- `deployment/` — Docker / Compose / Helm 部署资产
- `infrastructure/` — 配置、密钥、日志、追踪等平台基础设施

---

## 5. 项目阶段结论

**ICYQuant 的核心交易基础设施和机构级工程骨架已经基本形成。**

当前阶段最有价值的成果不是某一个 Strategy，而是已经形成完整链路：

```text
Research → Strategy → Signal → Risk Decision → Order → Execution → Position → Ledger → Reconciliation → Recovery
```

下一阶段应当从"继续堆功能"转向**部署、测试、验证和真实策略接入**：

```text
代码 → Docker → 本地部署 → 测试数据 → Paper Trading → 真实行情 → 策略接入 → 模拟交易 → 小资金验证 → Production
```

---

## 6. 相关文档

- 项目历史：[PROJECT_HISTORY.md](./PROJECT_HISTORY.md)
- 项目范围：[PROJECT_SCOPE.md](./PROJECT_SCOPE.md)
- 项目状态：[PROJECT_STATUS.md](./PROJECT_STATUS.md)
- 项目路线图：[PROJECT_ROADMAP.md](./PROJECT_ROADMAP.md)
- 产品需求：[../01-product/PRODUCT_REQUIREMENTS.md](../01-product/PRODUCT_REQUIREMENTS.md)
