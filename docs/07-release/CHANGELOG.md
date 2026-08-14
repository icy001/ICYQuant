# ICYQuant Changelog

> 本文档汇总 ICYQuant 的变更历史。仓库根目录 `CHANGELOG.md` 为权威详细版本，本文档为冻结摘要。

---

## v0.4.0-alpha2（2026-08）

### 新增

- 风险决策链收口：`RiskDecisionTrace`（frozen，8 字段）、`RiskDecisionAudit`（幂等）
- `RiskDecisionService.evaluate` 完整流程：context → rule_engine → decision → trace → audit → return
- Reconciliation 自愈生命周期（检测 / 分类 / 修复 / 验证 / 关闭）
- Control Plane：事故关联、告警、授权、审计
- Governance：决策台账、四眼审批、职责分离、政策评估
- 生产指标与遥测、告警引擎、事故管理、运行手册
- 完整文档冻结体系（docs/00-project ~ docs/07-release）

### 修复

- 模块同名解析（`audit` 包与 `audit.py`）兼容处理
- 历史决策可追溯性增强

### 变更

- 项目进入 Documentation Freeze，停止无限 Commit 扩张

---

## v0.4.0-alpha1（2026-07）

### 新增

- 平台基础：core、生产基础设施、日志与追踪平台、配置 / 密钥 / 加密平台、特性开关平台
- 服务框架：服务配置运行时、依赖注入、认证服务、用户服务、账户服务、组合服务、仓位服务、订单服务、执行网关、市场数据、策略运行时
- AI 与数据平台：agents / automl / data_platform / feature_engineering / mlops / message_queue / knowledge / ml / portfolio / rl / risk_intelligence / serving / lakehouse / storage / inference
- 11 个核心模块 GA 发布

---

## 相关文档

- 发布说明：[RELEASE_NOTES.md](./RELEASE_NOTES.md)
- 版本管理：[VERSIONING.md](./VERSIONING.md)
- 提交历史：[COMMIT_HISTORY.md](./COMMIT_HISTORY.md)
