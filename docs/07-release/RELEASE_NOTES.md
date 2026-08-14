# ICYQuant Release Notes

> 本文档记录 ICYQuant 各版本发布说明。

---

## v0.4.0-alpha2（当前，2026-08）

**版本状态：Development Phase Concluded / Documentation Freeze**

### 主要变化

- 交易域工程化收口（Commit 1 ~ 41）
- 风险决策链收口：Context → Rule Evaluation → Decision → Execution Gate → Trace → Audit
- `RiskDecisionTrace` 不可变追踪
- `RiskDecisionAudit` 幂等审计
- Reconciliation 自愈闭环
- Control Plane 事故管理、告警、治理
- 完整文档冻结体系（本目录）

### 覆盖范围

```text
基础设施 → 交易 Domain → Strategy → Risk → Order → Execution → Position → Ledger → Reconciliation → Research → Audit → Recovery
```

---

## v0.4.0-alpha1（2026-07）

**版本状态：GA（11 核心模块）**

### 主要变化

- 平台基础（core / 基础设施 / 日志追踪 / 配置密钥 / 特性开关）
- 服务框架（认证 / 用户 / 账户 / 组合 / 仓位 / 订单 / 执行网关 / 市场数据 / 策略运行时）
- AI 与数据平台（agents / automl / data_platform / feature_engineering / mlops / knowledge / ml / portfolio / rl / risk_intelligence / serving / lakehouse / storage / inference）
- 11 个核心模块 GA 发布

### 技术基线

- Python 3.12+
- PostgreSQL 16+
- Redis 7+
- Kafka 3.8+

---

## 相关文档

- 变更日志：[CHANGELOG.md](./CHANGELOG.md)
- 版本管理：[VERSIONING.md](./VERSIONING.md)
- 提交历史：[COMMIT_HISTORY.md](./COMMIT_HISTORY.md)
