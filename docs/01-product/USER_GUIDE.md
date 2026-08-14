# ICYQuant User Guide

> 本文档面向 ICYQuant 的使用者（Researcher / Strategy Developer / Trader / Risk / Ops），介绍如何使用系统能力。

---

## 1. 快速开始

### 1.1 本地启动

```bash
# 依赖
pip install -e .[dev]

# 数据库迁移
alembic upgrade head

# 启动 API
uvicorn apps.api.main:app --reload
```

### 1.2 健康检查

```bash
curl http://localhost:8000/health
curl http://localhost:8000/metrics
```

---

## 2. 角色使用指南

### 2.1 Quant Researcher

- 使用 Research 工作流构建因子与信号
- 使用 Backtest 引擎验证策略
- 使用 Attribution 分析绩效来源

### 2.2 Strategy Developer

- 定义策略（Load → Validate → Deploy → Run → Snapshot → Recovery）
- 生成信号并做信号验证
- 构造订单意图（OrderIntent）并通过 `OrderIntentValidator`

### 2.3 Trader / Execution

- 提交订单意图 → 订单生命周期管理
- 查看执行与成交
- 监控执行质量与滑点

### 2.4 Risk

- 配置风险政策（Risk Policy）与限额（Limit）
- 通过 `RiskDecisionService.evaluate` 获得 APPROVED / REJECTED
- 查看 `RiskDecisionTrace`（为什么通过 / 为什么拒绝）
- 发起 Recovery Request

### 2.5 Ops

- 使用控制网关（Control Gateway）：ALLOW / REDUCE_ONLY / BLOCK
- 查看告警与事故（Incident）生命周期
- 查看审计（Audit）记录

---

## 3. 核心操作流程

### 3.1 一笔完整交易

```text
1. 策略生成信号
2. 信号验证通过
3. 构造订单意图
4. 风险决策 evaluate → APPROVED
5. 生成订单
6. 提交执行
7. 成交 → Position 更新
8. Ledger 记账
9. Reconciliation 对账
```

### 3.2 风险拒绝场景

```text
1. 策略生成信号
2. 信号验证通过
3. 构造订单意图
4. 风险决策 evaluate → REJECTED（含原因与触发的规则）
5. 交易终止，生成审计记录
```

### 3.3 数据不一致恢复

```text
1. Reconciliation 检测到差异
2. 分类（Ledger≠Position / Position≠Execution / Event Missing / Duplicate）
3. 调查（Investigate）
4. 修复（Repair / Rebuild / Replay）
5. 验证（Verify）
6. 关闭（Close）
```

---

## 4. 常用 API 分组（apps/api v1）

- `/health`、`/metrics` — 健康与指标
- 控制网关 — 交易模式控制（ALLOW / REDUCE_ONLY / BLOCK）
- 事故与告警 — Incident / Alert 生命周期
- 治理 — 决策台账、审批、政策评估
- 业务域 — strategy / risk / order / execution / position / ledger / reconciliation 相关端点

> 详细 API 清单见现有 `docs/api/` 与 `docs/architecture/` 系列。

---

## 5. 安全使用须知

- 使用前需通过 Authentication / RBAC 授权
- 敏感操作会进入 Audit 记录
- 所有交易操作遵循 Idempotency 约定
- 生产环境请使用 Docker 部署（见 [../03-operations/DOCKER_DEPLOYMENT.md](../03-operations/DOCKER_DEPLOYMENT.md)）

---

## 6. 相关文档

- 交易工作流：[TRADING_WORKFLOW.md](./TRADING_WORKFLOW.md)
- 风控规范：[RISK_CONTROL_SPEC.md](./RISK_CONTROL_SPEC.md)
- 开发指南：[../05-development/DEVELOPMENT_GUIDE.md](../05-development/DEVELOPMENT_GUIDE.md)
