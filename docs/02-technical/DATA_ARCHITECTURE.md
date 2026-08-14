# ICYQuant Data Architecture

> 本文档描述 ICYQuant 的数据架构：存储分层、事件流、迁移与数据生命周期。

---

## 1. 存储分层

| 层 | 技术 | 用途 |
|----|------|------|
| 主数据库 | PostgreSQL 16+ | 业务状态、领域实体、事件存储 |
| 缓存 / 限流 | Redis 7+ | 缓存、限流、分布式锁 |
| 事件总线 | Kafka 3.8+ | 事件发布 / 订阅 |
| 嵌入式（测试） | SQLite / In-memory | 单元测试与组件测试 |

---

## 2. 数据分类

```text
业务状态数据（Order / Position / Ledger / Risk Decision）
    +
事件流数据（Event Store）
    +
配置数据（configs/）
    +
审计数据（Audit）
    +
研究数据（Factor / Backtest / Attribution）
```

---

## 3. 事件流数据

- 事件存储抽象：`services/event_store`
- 事件具备：Event ID / Aggregate ID / Event Type / Timestamp / Version / Payload / Correlation ID / Causation ID
- 事件流支持确定性 Replay

---

## 4. 数据库迁移

- 使用 **alembic** 管理 schema 迁移
- 迁移目录：`alembic/`
- 配置：`alembic.ini`

```bash
alembic upgrade head    # 升级到最新
alembic downgrade -1    # 回退一步
```

---

## 5. 数据生命周期

```text
产生（Event / 业务写入）
    ↓
持久化（幂等写入）
    ↓
投影（查询视图）
    ↓
对账（Reconciliation）
    ↓
归档 / 备份
    ↓
恢复（Replay / Restore）
```

---

## 6. 一致性机制

- 复式记账（借贷平衡）
- Reconciliation 检测：Ledger ≠ Position / Position ≠ Execution / Execution ≠ Order
- 事件缺失 / 重复检测
- 幂等写入防重放

---

## 7. 相关文档

- 数据库运维：[../03-operations/DATABASE.md](../03-operations/DATABASE.md)
- 备份与恢复：[../03-operations/BACKUP_RECOVERY.md](../03-operations/BACKUP_RECOVERY.md)
- 事件驱动架构：[EVENT_DRIVEN_ARCHITECTURE.md](./EVENT_DRIVEN_ARCHITECTURE.md)
- 配置：[../03-operations/CONFIGURATION.md](../03-operations/CONFIGURATION.md)
