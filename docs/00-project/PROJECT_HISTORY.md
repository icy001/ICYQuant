# ICYQuant Project History

> 本文档记录 ICYQuant 从工程起点到 v0.4.0-alpha2 / Commit 41 的发展历程。

---

## 1. 阶段总览

| 阶段 | 时间 | 版本 | 说明 |
|------|------|------|------|
| 平台起步 | — | v0.4.0-alpha1 | 基础设施、AI 平台、服务框架（Commit 1~35 阶段） |
| 服务体系 | — | v0.4.0-alpha1 GA | 11 个核心模块 GA 发布（2026-07-30） |
| 交易域收口 | — | v0.4.0-alpha2 | Commit 1 ~ 41：交易链路工程化收口 |
| 文档冻结 | 2026-08 | v0.4.0-alpha2 | 本文档体系（Documentation Freeze） |

---

## 2. 平台起步阶段（v0.4.0-alpha1）

以**机构级 AI 量化操作系统**为目标，完成平台基础建设：

- **Commit 1~5（v0.4.0-alpha2 系列的基础，编号始于 v0.4.0-alpha1）**
  - `060d9c1` — 平台基础（core）
  - `63c08fe` — 生产基础设施层
  - `dcf2e08` — 日志与追踪平台
  - `8feb09f` — 配置、密钥与加密平台
  - `efa1c5f` — 特性开关平台（Commit 5）

- **服务框架（v0.4.0-alpha1）**
  - 服务配置运行时、依赖注入框架
  - 认证服务、用户服务、账户服务、组合服务
  - 仓位服务、订单服务、执行网关、市场数据、策略运行时
  - 平台基础设施服务（Parts 23-35）

- **AI 与数据平台（v0.4.0-alpha1）**
  - agents / automl / data_platform / feature_engineering / mlops
  - message_queue / knowledge / ml / portfolio / rl / risk_intelligence / serving
  - lakehouse、storage、inference 等子模块

- **GA 发布（10476e7）**
  - `v0.4.0-alpha1 GA`：11 个核心模块（Research / AI / Backtest / OMS / EMS / Risk / Portfolio / Lakehouse / Observability / Security / Platform）
  - Python 3.12+、PostgreSQL 16+、Redis 7+、Kafka 3.8+

---

## 3. 交易域工程化收口阶段（v0.4.0-alpha2, Commit 1~41）

这一阶段聚焦把交易链路从"模块存在"推进到"工程化收口"。

> 特别澄清：**Commit 41 Part 1.1 ~ 1.5 并不是 5 个 Commit**，而是同一个 Commit 41 的 5 个部分。因此本阶段仍然是 **41 个 Commit**，不是 45 个。

### 3.1 基础设施与事件域（Commit 1~2）

- 平台基础与基础设施层
- 事件存储、日志与追踪平台

### 3.2 策略与信号（Commit 早期）

- 策略引擎（Load → Validate → Deploy → Run → Snapshot → Recovery）
- 信号引擎、信号验证、订单意图验证、组合决策

### 3.3 风控决策链（Commit 39~41 收口）

- 风险决策上下文 → 政策评估 → 决策 → 记录 → 追踪 → 审计 → 事件发布
- `RiskDecisionTrace`（不可变追踪）
- `RiskDecisionAudit`（幂等审计，只记录不重算）
- Replay 对比与确定性重放

### 3.4 控制平面与治理（Commit 24~29 及后续）

- 控制网关（ALLOW / REDUCE_ONLY / BLOCK）、fail-closed 准入
- 自愈事故控制平面（检测、关联、生命周期、升级、命令、缓解、审计、复盘）
- 治理决策台账、四眼审批、职责分离、确定性政策评估

### 3.5 运维与运营（Commit 30 后）

- 生产指标与遥测、告警引擎、事故管理、运行手册
- 服务注册与发现、心跳、健康检查、租约管理

### 3.6 对账与自愈（Commit 40）

- 差异检测、分类、修复计划、修复执行、恢复审计、自愈生命周期

---

## 4. 文档冻结阶段（2026-08）

- 停止无限 Commit 扩张
- 建立正式文档体系（`docs/00-project` ~ `docs/07-release`）
- 下一阶段转向：文档化 → 部署 → 集成 → 测试 → Paper Trading → 生产验证

---

## 5. 关键节点时间线

```text
v0.4.0-alpha1（平台起步）
      ↓
Commit 1 ~ 35（v0.4.0-alpha1 服务与 AI 平台）
      ↓
v0.4.0-alpha1 GA（2026-07-30，11 模块 GA）
      ↓
Commit 1 ~ 41（v0.4.0-alpha2，交易域工程化收口）
      ↓
Documentation Freeze（2026-08，项目阶段收口）
```

---

## 6. 相关文档

- 项目总览：[PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md)
- 提交历史：[../07-release/COMMIT_HISTORY.md](../07-release/COMMIT_HISTORY.md)
- 版本说明：[../07-release/VERSIONING.md](../07-release/VERSIONING.md)
