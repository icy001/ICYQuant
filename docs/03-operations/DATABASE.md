# ICYQuant Database

> 本文档描述 ICYQuant 的数据库设计与运维。

---

## 1. 数据库

| 项 | 值 |
|----|----|
| 主数据库 | PostgreSQL 16+ |
| 缓存 / 锁 | Redis 7+ |
| 测试 | SQLite / In-memory |
| 迁移 | alembic |

---

## 2. Schema 管理

```bash
alembic upgrade head        # 升级到最新
alembic downgrade -1        # 回退一步
alembic revision -m "..."   # 新建迁移
```

迁移目录：`alembic/`，配置：`alembic.ini`。

---

## 3. 数据域

```text
业务状态（Order / Position / Ledger / Risk Decision）
    +
事件流（Event Store）
    +
审计（Audit）
    +
配置（configs/）
```

---

## 4. 一致性

- 事务保证关键写入原子性
- 复式记账借贷平衡约束
- Reconciliation 检测跨域不一致
- 幂等写入（决策 ID / 事件 ID 唯一）

---

## 5. 运维建议

### 5.1 备份

- 定期全量备份 + WAL 归档
- 备份验证（恢复演练）
- 详见 [BACKUP_RECOVERY.md](./BACKUP_RECOVERY.md)

### 5.2 监控

- 连接数、慢查询、主从延迟
- 磁盘使用率与增长趋势

### 5.3 连接池

- 配置合理的连接池大小
- 避免连接泄漏

---

## 6. 常见问题

| 问题 | 处理 |
|------|------|
| 迁移冲突 | 先 review 再 upgrade，冲突时人工解决 |
| 慢查询 | 通过监控发现，优化索引 / 查询 |
| 数据不一致 | 触发 Reconciliation 检测与修复 |

---

## 7. 相关文档

- 数据架构：[../02-technical/DATA_ARCHITECTURE.md](../02-technical/DATA_ARCHITECTURE.md)
- 配置：[CONFIGURATION.md](./CONFIGURATION.md)
- 备份恢复：[BACKUP_RECOVERY.md](./BACKUP_RECOVERY.md)
