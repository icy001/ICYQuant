# ICYQuant 使用文档

> 面向 v0.4.0-alpha2 已部署环境（Docker Compose，10 服务健康）的完整使用指南

## 目录

- [1. 系统概览](#1-系统概览)
  - [服务清单与端口](#服务清单与端口)
  - [数据卷](#数据卷)
- [2. 快速开始](#2-快速开始)
- [3. 服务状态查看](#3-服务状态查看)
- [4. HTTP API 使用](#4-http-api-使用)
  - [核心端点](#核心端点)
  - [交互式文档](#交互式文档)
- [5. 验证 CLI 使用](#5-验证-cli-使用)
  - [Golden Scenarios（场景回归）](#golden-scenarios场景回归)
  - [Paper Trading（模拟盘）](#paper-trading模拟盘)
  - [Shadow Trading（影子交易）](#shadow-trading影子交易)
  - [Strategy Gate（研究层回测门禁）](#strategy-gate研究层回测门禁)
  - [Readiness Gate（生产就绪门禁）](#readiness-gate生产就绪门禁)
- [6. 日常运维](#6-日常运维)
  - [启动 / 停止 / 重启](#启动--停止--重启)
  - [日志查看](#日志查看)
  - [代码更新与重建](#代码更新与重建)
  - [监控](#监控)
- [7. 数据持久化与备份](#7-数据持久化与备份)
- [8. 常见问题排查](#8-常见问题排查)
- [9. 命令速查表](#9-命令速查表)

---

## 1. 系统概览

### 服务清单与端口

| 服务名 | 容器名 | 端口 | 说明 |
|--------|--------|------|------|
| `api` | `icyquant-api` | 8000 | FastAPI 网关（主入口） |
| `database` | `icyquant-database` | 5432 | PostgreSQL 16 |
| `event-bus` | `icyquant-event-bus` | 6379 | Redis 事件总线 |
| `strategy-runtime` | `icyquant-strategy-runtime` | 8011 | 策略运行时健康端点 |
| `risk-engine` | `icyquant-risk-engine` | 8012 | 风控引擎健康端点 |
| `order-engine` | `icyquant-order-engine` | 8013 | 订单引擎健康端点 |
| `execution-engine` | `icyquant-execution-engine` | 8014 | 执行引擎健康端点 |
| `position-ledger` | `icyquant-position-ledger` | 8015 | 持仓账本健康端点 |
| `reconciliation` | `icyquant-reconciliation` | 8016 | 对账引擎健康端点 |
| `monitoring` | `icyquant-monitoring` | 9090 | Prometheus |

> 6 个引擎服务（8011-8016）提供独立健康检查端点；对外业务入口统一走 `api:8000`。

### 数据卷

| 卷名 | 挂载点 | 内容 |
|------|--------|------|
| `postgres_data` | `/var/lib/postgresql/data` | PostgreSQL 数据 |
| `prometheus_data` | `/prometheus` | 指标数据 |

数据卷由 Docker 管理，`docker compose down` 不会删除，`down -v` 才会清空。

---

## 2. 快速开始

```bash
cd /Users/xuehairong/CodeBuddy/20260817155030/ICYQuant

# 一键三连验证：服务状态 → 场景回归 → 就绪门禁
docker compose ps
docker exec icyquant-api python -m apps.runtime scenarios
docker exec icyquant-api python -m apps.runtime gate
```

期望输出：

- `docker compose ps`：10 个服务全部 `(healthy)`
- `scenarios`：`GATE: PASS (8/8)`
- `gate`：`PHASE 6 PRODUCTION READINESS GATE: PASS (21/21)`

---

## 3. 服务状态查看

```bash
# 完整状态列表
docker compose ps

# 精简表格（仅名称 + 状态）
docker compose ps --format "table {{.Name}}\t{{.Status}}"

# 仅显示非健康服务
docker compose ps | grep -v "(healthy)" | grep -v "^NAME"

# 聚合健康检查（HTTP）
curl -s http://localhost:8000/health | python3 -m json.tool
```

健康端点返回 `{"status": "READY", ...}` 时表示 10 个逻辑服务全部 UP。

---

## 4. HTTP API 使用

### 核心端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 服务名称、版本、文档地址 |
| `/health` | GET | 聚合健康（10 服务真实探测） |
| `/ready` | GET | 就绪探针 `{"ready": true/false}` |
| `/version` | GET | 版本、环境、状态 |
| `/status` | GET | Bootstrap 运行报告 |
| `/metrics` | GET | Prometheus 指标（text/plain） |
| `/health/database` | GET | 数据库健康详情 |
| `/docs` | GET | Swagger UI 交互文档 |
| `/redoc` | GET | ReDoc 文档 |

常用示例：

```bash
# 健康检查
curl http://localhost:8000/health

# 版本信息
curl http://localhost:8000/version
# {"version": "0.4.0-alpha2", "env": "production", "status": "stable"}

# 数据库健康
curl http://localhost:8000/health/database

# 就绪状态（脚本判断用，返回码 200 即就绪）
curl -fsS http://localhost:8000/ready
```

### 交互式文档

浏览器打开以下地址即可查看 / 调试全部 API：

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>

---

## 5. 验证 CLI 使用

所有验证命令在 `api` 容器内执行。统一入口：

```bash
docker exec icyquant-api python -m apps.runtime <子命令> [--json]
```

各子命令均支持 `--json` 输出结构化结果，便于脚本解析（如 `| jq .`）。

### Golden Scenarios（场景回归）

8 个黄金场景全量回归，验证核心交易链路。

```bash
# 标准输出（人类可读）
docker exec icyquant-api python -m apps.runtime scenarios

# 结构化输出
docker exec icyquant-api python -m apps.runtime scenarios --json
```

### Paper Trading（模拟盘）

模拟盘成交验证：延迟、滑点、成交/拒单/错误率、权益。

```bash
# 默认 50 个信号
docker exec icyquant-api python -m apps.runtime paper

# 自定义信号数量
docker exec icyquant-api python -m apps.runtime paper --signals 200

# 结构化输出
docker exec icyquant-api python -m apps.runtime paper --json
```

关键指标解读：

| 指标 | 含义 | 参考健康值 |
|------|------|-----------|
| `fill_rate_pct` | 成交率 | ~80% |
| `reject_rate_pct` | 拒单率 | ~18% |
| `error_rate_pct` | 错误率 | < 5% |
| `latency_total_us_avg` | 全链路平均延迟 | ~60μs |
| `slippage_bps_avg` | 平均滑点 | ~3 bps |
| `equity` | 期末权益 | 随信号波动 |

### Shadow Trading（影子交易）

将信号流镜像到隔离影子轨道，验证主/影子状态一致性。

```bash
# 默认 20 个信号
docker exec icyquant-api python -m apps.runtime shadow

# 自定义信号数量
docker exec icyquant-api python -m apps.runtime shadow --signals 100

# 结构化输出
docker exec icyquant-api python -m apps.runtime shadow --json
```

退出码 `0` 表示全部一致（`N/N consistent`），`1` 表示存在分歧。

### Strategy Gate（研究层回测门禁）

Phase 7：Research Layer 端到端回测——Strategy 001（S001，NVDA 15m 双均线金叉/死叉）
加载 `data/lakehouse/NVDA_15m.csv` → 回测引擎 → 绩效报告，验证研究层已接入部署栈。

前置：数据文件需同步进容器（宿主 `data/lakehouse/NVDA_15m.csv` 已生成，重新生成用
`python infra/scripts/generate_nvda_15m.py`）。

```bash
# 同步数据到容器（若尚未同步）
docker cp data/lakehouse icyquant-api:/app/data/

# 运行 Strategy Gate（6 项检查）
docker exec icyquant-api python -m apps.runtime strategy

# 结构化输出
docker exec icyquant-api python -m apps.runtime strategy --json
```

退出码 `0` 表示全部通过（6/6），`1` 表示存在失败。结果同时纳入 Readiness Gate 的
V-03 检查项。

### Readiness Gate（生产就绪门禁）

22 项检查覆盖 6 大类：Infrastructure / Trading / Security / Operations / Validation 等。

```bash
# 完整报告（含每项明细）
docker exec icyquant-api python -m apps.runtime gate

# 结构化输出
docker exec icyquant-api python -m apps.runtime gate --json
```

通过标准：`PASS (22/22)`。退出码 `0` 为通过。

---

## 6. 日常运维

### 启动 / 停止 / 重启

```bash
cd /Users/xuehairong/CodeBuddy/20260817155030/ICYQuant

# 启动全部服务（已存在则跳过）
docker compose up -d

# 重启单个服务
docker compose restart api
docker compose restart risk-engine

# 暂停全部（保留数据卷）
docker compose stop

# 恢复运行
docker compose start

# 完全停止并移除容器（保留数据卷）
docker compose down

# 注意：down -v 会删除数据卷，数据将丢失，谨慎使用！
```

### 日志查看

```bash
# 跟踪单个服务日志
docker compose logs -f api
docker compose logs -f risk-engine

# 查看最近 100 行
docker compose logs --tail 100 api

# 按时间过滤
docker compose logs --since 10m api
```

### 代码更新与重建

源码（`apps/` 等）是 COPY 进镜像的，改动后需重建：

```bash
cd /Users/xuehairong/CodeBuddy/20260817155030/ICYQuant

# 重建单个服务镜像并滚动重启
docker compose up -d --force-recreate api

# 重建全部服务
docker compose build
docker compose up -d --force-recreate
```

> 提示：重建期间服务会短暂中断，生产环境建议低峰期操作。

### 监控

| 工具 | 地址 | 用途 |
|------|------|------|
| Prometheus | <http://localhost:9090> | 指标查询、目标状态 |
| Prometheus 自检 | <http://localhost:9090/-/healthy> | 探活 |
| API 指标 | <http://localhost:8000/metrics> | 业务指标 |

Prometheus 常用查询：

```text
up                          # 所有 scrape 目标状态
rate(icyquant_*[5m])        # 各类业务指标速率
```

---

## 7. 数据持久化与备份

### 数据库备份 / 恢复

```bash
# 备份（宿主机执行）
docker exec icyquant-database pg_dump -U postgres -F c -b -v postgres > backup_$(date +%Y%m%d_%H%M%S).dump

# 恢复
cat backup.dump | docker exec -i icyquant-database pg_restore -U postgres -d postgres
```

### 卷管理

```bash
# 查看卷
docker volume ls | grep icyquant

# 卷大小（进入容器查看）
docker exec icyquant-database du -sh /var/lib/postgresql/data
```

---

## 8. 常见问题排查

### 服务未健康

```bash
docker compose ps | grep -v healthy
docker compose logs --tail 50 <服务名>   # 查看崩溃原因
```

常见原因与处理：

| 症状 | 可能原因 | 处理 |
|------|----------|------|
| 容器频繁重启 | 环境变量缺失 | 检查 `docker-compose.yml` 中该服务环境变量 |
| 数据库连接失败 | 数据库未就绪 | `docker compose restart database`，等待 30s 后重启依赖服务 |
| 端口被占用 | 本地进程占用 | 检查 `lsof -i :端口` 并处理 |
| 镜像拉取失败 | 网络/Docker Hub 受限 | 已配置镜像加速器，重试 `docker compose pull` |

### Gate 单项失败

```bash
docker exec icyquant-api python -m apps.runtime gate --json | jq '.categories[] | .items[] | select(.passed == false)'
```

定位失败项后按 `detail` 字段提示处理；若是代码问题，见「代码更新与重建」。

### 容器内网络不通

引擎间通信使用 Compose 服务名（如 `risk-engine:8012`），**不要**用 `localhost`（容器内指向自身）。

### Docker daemon 异常

```bash
docker info          # 查看 daemon 状态
# 异常时重启 Docker Desktop（macOS）/ docker service restart docker（Linux）
```

---

## 9. 命令速查表

```bash
# === 状态 ===
docker compose ps                                          # 服务状态
curl http://localhost:8000/health                          # 聚合健康

# === 验证 ===
docker exec icyquant-api python -m apps.runtime scenarios  # Golden 8/8
docker exec icyquant-api python -m apps.runtime paper      # 模拟盘
docker exec icyquant-api python -m apps.runtime shadow     # 影子交易
docker exec icyquant-api python -m apps.runtime strategy   # Strategy 001 回测
docker exec icyquant-api python -m apps.runtime gate       # 就绪门禁 22/22

# === 运维 ===
docker compose logs -f <服务名>                             # 日志
docker compose restart <服务名>                             # 重启
docker compose up -d --force-recreate <服务名>              # 重建并重启
docker compose stop / start                                # 整体暂停/恢复
docker compose down                                        # 停止（保留数据）

# === 监控 ===
curl http://localhost:9090/-/healthy                       # Prometheus 探活
curl http://localhost:8000/metrics                         # 业务指标
```
