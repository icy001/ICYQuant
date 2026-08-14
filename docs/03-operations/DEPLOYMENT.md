# ICYQuant Deployment

> 本文档描述 ICYQuant 的部署结构与环境要求。

---

## 1. 推荐部署结构

```text
                    Internet / Internal Network
                              │
                              ▼
                         API Gateway
                              │
                 ┌────────────┴────────────┐
                 │                         │
             API Service              Admin / UI
                 │
                 ▼
             Core Engine
                 │
       ┌─────────┼─────────┐
       │         │         │
    Strategy    Risk     Order
       │         │         │
       └─────────┼─────────┘
                 │
              Event Bus
                 │
       ┌─────────┴─────────┐
       │                   │
   Database            Audit Store
```

---

## 2. 环境要求

| 组件 | 版本 |
|------|------|
| Python | 3.12+ |
| PostgreSQL | 16+ |
| Redis | 7+ |
| Kafka | 3.8+ |
| Docker | 20+（可选但推荐） |

---

## 3. 部署步骤

### 3.1 基础部署

```bash
# 1. 依赖安装
pip install -e .[dev]

# 2. 数据库迁移
alembic upgrade head

# 3. 启动 API
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000

# 4. 启动 Worker（消费事件）
python -m apps.worker
```

### 3.2 生产部署

生产环境推荐使用 Docker Compose（见 [DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)）。

---

## 4. 配置

所有配置通过 `configs/`（YAML）+ 环境变量注入：

- 数据库连接
- Redis 连接
- Kafka 连接
- 日志级别
- 特性开关

详见 [CONFIGURATION.md](./CONFIGURATION.md)。

---

## 5. 部署验证

```text
1. 健康检查：GET /health
2. 指标：GET /metrics
3. 事件链路：发布一条测试事件，验证消费者
4. 幂等验证：重复投递不产生重复副作用
```

---

## 6. 部署形态对比

| 形态 | 适用场景 |
|------|----------|
| 本地开发 | 直接运行（uvicorn + 嵌入式组件） |
| Docker Compose | 单机 / 小规模（推荐起步） |
| Kubernetes / Helm | 大规模（deployment/ 提供资产） |
| Terraform | 云上基础设施（deployment/） |

---

## 7. 相关文档

- Docker 部署：[DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)
- 配置：[CONFIGURATION.md](./CONFIGURATION.md)
- 数据库：[DATABASE.md](./DATABASE.md)
- 生产运行手册：[PRODUCTION_RUNBOOK.md](./PRODUCTION_RUNBOOK.md)
