# ICYQuant Development Guide

> 本文档是 ICYQuant 开发指南。

---

## 1. 开发流程

```text
Issue
 ↓
Design
 ↓
Implementation
 ↓
Unit Test
 ↓
Integration Test
 ↓
Regression
 ↓
Commit
 ↓
Review
 ↓
Release
```

---

## 2. 核心开发原则

### Domain First

先定义业务语义，再实现代码。

### Explicit State

重要状态必须显式建模（Order / Position / Risk Decision 等均为显式状态机）。

### Idempotency

交易系统操作必须尽量保证幂等。

### Immutable Audit

审计记录不可随意修改。

### Deterministic Replay

相同输入应该得到可解释、可重复的结果。

---

## 3. 环境搭建

```bash
# 依赖
pip install -e .[dev]

# 测试
pytest tests/

# 数据库迁移
alembic upgrade head

# 启动
uvicorn apps.api.main:app --reload
```

---

## 4. 代码结构

| 目录 | 说明 |
|------|------|
| `services/` | 业务域服务（strategy / risk / order / execution / position / ledger / reconciliation / control_plane / event_store / eventbus / governance / attribution） |
| `apps/` | FastAPI 应用（api / worker） |
| `core/` | 核心基础（BaseEntity / DomainEvent 等） |
| `contracts/` | 共享契约 |
| `infrastructure/` | 平台基础设施（配置 / 密钥 / 日志 / 追踪） |
| `tests/` | 测试套件 |
| `alembic/` | 数据库迁移 |

---

## 5. 新增功能流程

```text
1. 明确 Domain 边界与职责
2. 定义显式状态 / 事件
3. 实现 Service
4. 保证幂等与可重放
5. 编写测试（含 Recovery / Replay）
6. 运行全量回归
7. 提交 Commit
```

---

## 6. 提交规范

- 一个提交一个逻辑变更
- Commit message 描述变更内容
- 变更必须通过测试

---

## 7. 相关文档

- 代码风格：[CODE_STYLE.md](./CODE_STYLE.md)
- 测试：[TESTING.md](./TESTING.md)
- 分支流程：[GIT_WORKFLOW.md](./GIT_WORKFLOW.md)
- 贡献指南：[CONTRIBUTING.md](./CONTRIBUTING.md)
