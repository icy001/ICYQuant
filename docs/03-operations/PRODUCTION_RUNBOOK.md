# ICYQuant Production Runbook

> 本文档是生产环境的操作手册：日常操作、常见问题与处置流程。

---

## 1. 日常操作

### 1.1 启动 / 停止

```bash
docker compose up -d          # 启动
docker compose down           # 停止
docker compose restart api    # 重启某服务
```

### 1.2 健康检查

```bash
curl http://localhost:8000/health
curl http://localhost:8000/metrics
```

### 1.3 数据库迁移

```bash
alembic upgrade head
```

---

## 2. 常用检查清单

| 检查项 | 方法 |
|--------|------|
| 服务健康 | /health |
| 队列积压 | 监控 Queue Lag |
| 数据一致性 | Reconciliation 状态 |
| 告警 | 告警面板 |
| 备份 | 最近备份时间 |

---

## 3. 常见故障处置

### 3.1 API 响应慢

1. 查看 P99 延迟指标
2. 检查数据库连接与慢查询
3. 检查 Redis 缓存命中
4. 检查队列积压

### 3.2 事件处理停滞

1. 检查 Kafka 消费者状态
2. 检查 Worker 日志
3. 检查死信 / 重试队列

### 3.3 数据不一致

1. 触发 Reconciliation 检测
2. 分类差异
3. 执行修复 / 重建 / 重放
4. 验证一致

### 3.4 需要紧急遏制

1. 控制网关切到 REDUCE_ONLY 或 BLOCK
2. 通知相关方
3. 调查根因

---

## 4. 恢复后操作

```text
1. 验证状态一致（Reconciliation）
2. 验证审计完整
3. 确认无重复副作用（幂等）
4. 复盘并更新 Runbook
```

---

## 5. 相关文档

- 部署：[DEPLOYMENT.md](./DEPLOYMENT.md)
- 监控：[MONITORING.md](./MONITORING.md)
- 事故响应：[INCIDENT_RESPONSE.md](./INCIDENT_RESPONSE.md)
- 备份恢复：[BACKUP_RECOVERY.md](./BACKUP_RECOVERY.md)
