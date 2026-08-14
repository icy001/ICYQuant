# ICYQuant Docker Deployment

> 本文档描述 ICYQuant 的 Docker / Docker Compose 部署。

---

## 1. 部署策略

**第一阶段推荐：Docker + Docker Compose**，而不是一开始就 Kubernetes。

典型服务编排：

```text
docker-compose.yml

services:
  api:
  strategy:
  risk:
  order:
  execution:
  database:
  event-bus:
  monitoring:
```

---

## 2. 优势

在以下环境之间保持一致性：

- Windows
- Mac mini
- Linux Server
- Cloud VM

```bash
docker compose up -d          # 启动
docker compose ps             # 查看状态
docker compose logs -f        # 查看日志
docker compose down           # 停止
```

---

## 3. 核心容器

| 服务 | 说明 |
|------|------|
| `api` | FastAPI 网关 |
| `worker` | 事件消费者 |
| `database` | PostgreSQL 16+ |
| `event-bus` | Kafka 3.8+（可选 Redis） |
| `monitoring` | 指标与告警 |

---

## 4. 数据持久化

- 数据库使用 volume 持久化
- 迁移在容器启动时执行（alembic）
- 审计与事件流随数据库持久化

---

## 5. 环境变量

通过 `.env` 注入：

```text
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
KAFKA_BOOTSTRAP_SERVERS=...
LOG_LEVEL=INFO
```

---

## 6. 生产注意

- 不要在容器内保存状态（无状态 API / Worker）
- 数据库独立 volume 备份
- 密钥使用 secrets 管理，不写入镜像
- 健康检查与优雅停机配置

---

## 7. 相关文档

- 部署总览：[DEPLOYMENT.md](./DEPLOYMENT.md)
- 配置：[CONFIGURATION.md](./CONFIGURATION.md)
- 监控：[MONITORING.md](./MONITORING.md)
- 备份恢复：[BACKUP_RECOVERY.md](./BACKUP_RECOVERY.md)
