# ICYQuant v0.4.0
# Deployment & Validation Runbook

> 本 Runbook 是 v0.4.0-alpha2 部署与验收的**唯一官方流程**。
> 自本文件生效之日起，不再依赖聊天记录中的散落命令。
> 从第 1 节开始逐关执行，每关通过后再进入下一关；任一一关 FAIL 则停止并排障（见第 22 节）。

---

## 1. 目标与适用范围

- 交付版本：**ICYQuant v0.4.0-alpha2**
- 覆盖范围：本地开发运行、Docker Compose 全量部署、Golden Scenarios、Production Readiness Gate、Dashboard Gate、Adapter Layer Gate、Paper/Shadow Trading 验证。
- 适用范围：具备 Python 3.12 + Docker 的开发机/测试服务器（Windows / macOS / Linux）。
- 总览：
  - Deployment 健康检查：10/10 服务
  - Golden Scenarios：8/8
  - Production Readiness Gate：21/21
  - Dashboard Gate：15/15（D-01 ~ D-15）
  - Adapter Layer Gate：12/12（A-01 ~ A-12）

## 2. 版本基线

| 项 | 值 | 校验方式 |
|---|---|---|
| 应用版本 | `0.4.0-alpha2` | `VERSION` 文件、`shared.constants.APP_VERSION` |
| Gate 版本 | `0.4.0-alpha2` | `GATE_VERSION`（`apps/runtime/readiness_gate.py`） |
| 镜像标签 | `icyquant:0.4.0-alpha2` | `docker-compose.yml` |
| 分支 | `develop` | `git branch --show-current` |

版本不对齐（Validation V-02 失败）时，禁止进入生产验收。

## 3. 环境要求

| 依赖 | 最低版本 | 备注 |
|---|---|---|
| Python | 3.12 | 3.11 以下不受支持 |
| Docker | 20.10+ | 含 Docker Compose v2 |
| Git | 任意现代版本 | |
| 端口占用 | 见下表 | 冲突时见 22.1 |

**端口清单**

| 端口 | 用途 |
|---|---|
| 5432 | PostgreSQL 16（database） |
| 6379 | Redis 7（event-bus） |
| 8000 | API / Dashboard |
| 8010 | Runtime 健康服务（本地独立运行） |
| 8011~8016 | 六引擎健康端口（strategy-runtime/risk-engine/order-engine/execution-engine/position-ledger/reconciliation） |
| 9090 | Prometheus（monitoring） |

## 4. 获取代码

```bash
# Windows PowerShell
cd d:\PycharmProjects\ICYQuant
git checkout develop
git pull --rebase origin develop

# macOS / Linux
cd ~/projects/ICYQuant
git checkout develop
git pull --rebase origin develop
```

确认工作区干净：

```bash
git status          # 期望：nothing to commit, working tree clean
```

## 5. 本地开发环境搭建

> 若只跑容器化部署（第 10 节起），可跳过本节；跑 Gate / 测试必须执行。

```bash
# Windows PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[all]"

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[all]"
```

验证安装：

```bash
python -c "from apps.api.main import app; print('api app OK')"
python -m apps.runtime health --help     # 打印 5 个子命令说明
```

## 6. 本地数据库与消息总线

仅容器化部署（第 10 节）时无需单独启动；本地直连 API 需先起基础设施：

```bash
docker compose up -d database event-bus
docker compose ps                         # database/event-bus 应为 healthy
```

## 7. 数据库迁移

```bash
alembic upgrade head
```

幂等操作，可重复执行。失败时见 22.4。

## 8. 本地启动 API

```bash
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
```

- Dashboard：`http://localhost:8000/dashboard/`
- 健康端点：`http://localhost:8000/health`
- API 文档：`http://localhost:8000/docs`

## 9. 本地启动 Runtime 健康服务（可选）

```bash
python -m apps.runtime health --port 8010
# 验证
curl http://localhost:8010/health
```

## 10. Docker Compose 部署（完整系统）

```bash
docker compose up -d --build
docker compose ps
```

**10 个服务清单**

| 服务 | 容器名 | 健康端口 | 说明 |
|---|---|---|---|
| database | icyquant-database | 5432 | PostgreSQL 16 |
| event-bus | icyquant-event-bus | 6379 | Redis 7 |
| api | icyquant-api | 8000 | API + Dashboard，启动时自动 `alembic upgrade head` |
| strategy-runtime | icyquant-strategy-runtime | 8011 | 策略运行时 |
| risk-engine | icyquant-risk-engine | 8012 | 风控引擎 |
| order-engine | icyquant-order-engine | 8013 | 订单引擎 |
| execution-engine | icyquant-execution-engine | 8014 | 执行引擎 |
| position-ledger | icyquant-position-ledger | 8015 | 持仓账本 |
| reconciliation | icyquant-reconciliation | 8016 | 对账服务 |
| monitoring | icyquant-monitoring | 9090 | Prometheus |

期望结果：**10/10 服务 `healthy`**。

## 11. 部署后健康检查

```bash
curl http://localhost:8000/health
```

期望：`"status": "OK"` 且 10 个 service 全部 `"UP"`。

```bash
docker compose ps --format "table {{.Name}}\t{{.Status}}"
```

期望：全部 `healthy`（Deployment 验收 10/10）。

## 12. Golden Scenario 验收（8/8）

> 在容器内或本地（依赖已就绪）均可执行。

```bash
python -m apps.runtime scenarios
# 详细 JSON
python -m apps.runtime scenarios --json
```

期望输出：

```
GATE: PASS (8/8)
  Scenario 01 [PASS] ...
  ...
  Scenario 08 [PASS] ...
```

验收标准：**`GATE: PASS (8/8)`**。

## 13. Production Readiness Gate（21/21）

```bash
python -m apps.runtime gate
# 详细 JSON
python -m apps.runtime gate --json
```

Gate 六类检查项：

| 类别 | 检查项 | 数量 |
|---|---|---|
| Infrastructure | I-01 10 服务 UP、I-02 DB、I-03 Redis、I-04 Prometheus | 4 |
| Trading | T-01 Scenarios 8/8、T-02 Paper 指标、T-03 Shadow 10/10 | 3 |
| Reliability | R-01 重复事件、R-02 崩溃恢复、R-03 事件丢失重建、R-04 账本对账修复 | 4 |
| Security | S-01 生产模式、S-02 非默认密钥、S-03 审计日志、S-04 DB 内网寻址 | 4 |
| Operations | O-01 聚合健康、O-02 引擎健康端口、O-03 容器健康检查、O-04 Prometheus | 4 |
| Validation | V-01 Scenarios、V-02 版本对齐 0.4.0-alpha2 | 2 |

期望输出：**`PHASE 6 PRODUCTION READINESS GATE: PASS (21/21)`**。

> 注意：Gate 使用容器内服务名（如 `http://api:8000/health`）寻址，
> 因此**必须在 compose 网络内运行**（`docker compose exec api python -m apps.runtime gate` 或作为 API 容器内命令）。
> 本地裸跑若解析不到 `api/database/event-bus/monitoring` 主机名会失败，属预期行为。

## 14. Dashboard Gate（15/15）

> Dashboard 验收 D-01 ~ D-15：全部断言走 API Gateway（`apps.api.main:app`），与浏览器行为一致。

```bash
python -m pytest tests/test_dashboard_gate.py -v --import-mode=importlib
```

期望：**15 passed**（D-01 启动、D-02 认证、D-03 路由、D-04 Accounts、D-05 Orders、D-06 订单详情、D-07 Positions、D-08 Executions、D-09 Reconciliation、D-10 Critical Error、D-11 审计、D-12 会话控制、D-13 权限、D-14 静态资源、D-15 端口绑定/健康）。

> 必须带 `--import-mode=importlib`：`tests/platform/` 目录会遮蔽标准库模块，缺省 rootdir 模式可能导入失败（见 22.5）。

## 15. Adapter Layer Gate（12/12）

> 多账户 Adapter 验收 A-01 ~ A-12：A股/期货/美股/FX 四类账户走统一契约。

```bash
python -m pytest tests/test_adapter_gate.py -v --import-mode=importlib
```

期望：**12 passed**（A-01 账户领域、A-02 Broker 领域、A-03 路由、A-04 连接健康、A-05 余额、A-06 持仓、A-07 订单、A-08 成交、A-09 下单、A-10 撤单、A-11 同步、A-12 对账）。

## 16. 回归测试

关键回归集合（含本次交付的全部 Gate）：

```bash
python -m pytest tests/test_dashboard_gate.py tests/test_adapter_gate.py -q --import-mode=importlib
```

完整回归（耗时较长，可选）：

```bash
python -m pytest tests/ -q --import-mode=importlib
```

## 17. Paper Trading（Phase 4）

```bash
python -m apps.runtime paper --signals 50
# 详细 JSON
python -m apps.runtime paper --signals 50 --json
```

验收标准：`PHASE 4 PAPER TRADING - GATE: PASS`，且 `error_rate_pct < 100`。
关注指标：fill_rate_pct、reject_rate_pct、slippage_bps_avg、latency_total_us_avg。

## 18. Shadow Trading（Phase 5）

```bash
python -m apps.runtime shadow --signals 20
# 详细 JSON
python -m apps.runtime shadow --signals 20 --json
```

验收标准：`PHASE 5 SHADOW TRADING - GATE: PASS (20/20 consistent)`，且无 DIVERGENCE 输出。

## 19. Dashboard 手动验收

1. 打开 `http://localhost:8000/dashboard/`
2. 使用种子账号登录：

| 用户名 | 密码 | 角色 |
|---|---|---|
| `admin` | `admin123` | ADMIN |
| `trader` | `trader123` | TRADER |

3. 逐页核对（左侧导航）：
   - **Overview**：服务健康、关键指标、会话状态
   - **Strategies**：策略列表 + 详情（信号/风控决策/订单/成交联动）
   - **Orders**：订单列表（含 `account_id` 字段）+ 订单详情（全链路追踪）
   - **Executions**：成交记录（paper session 与多账户 Adapter 合并展示）
   - **Portfolio**：全局组合（多币种按演示汇率折算 USD 汇总）
   - **Accounts**：账户总览（A股/期货/美股/FX）+ 账户详情（余额/持仓/订单/成交）
   - **Reconciliation**：对账结果（含 Adapter 层 accounts 对账）
   - **Alerts**：告警列表
   - **System**：系统信息

4. 会话控制：可 Start/Stop paper session，订单可 Cancel。

## 20. 多账户 Adapter 手动验收

通过 API 直接验证（登录拿 token 后调用）：

```bash
# 登录
$body = '{"username":"admin","password":"admin123"}'
$r = Invoke-RestMethod -Uri http://localhost:8000/api/auth/login -Method Post -Body $body -ContentType 'application/json'
$h = @{ Authorization = "Bearer $($r.token)" }

# 1) 账户列表：期望 4 类账户
Invoke-RestMethod -Uri http://localhost:8000/dashboard/accounts -Headers $h

# 2) 账户详情（示例：FX 账户）
Invoke-RestMethod -Uri http://localhost:8000/dashboard/accounts/fx_01 -Headers $h

# 3) 全局组合（USD 聚合）
Invoke-RestMethod -Uri http://localhost:8000/dashboard/portfolio -Headers $h

# 4) 成交记录
Invoke-RestMethod -Uri http://localhost:8000/dashboard/executions -Headers $h

# 5) 对账（含 Adapter 层）
Invoke-RestMethod -Uri http://localhost:8000/dashboard/reconciliation -Headers $h

# 6) 手动同步（ADMIN；触发 Adapter SyncEngine + 审计）
Invoke-RestMethod -Uri http://localhost:8000/dashboard/accounts/sync -Method Post -Headers $h
```

验收标准：
- Accounts 展示 4 个账户（CN 股票 / CN 期货 / US 股票 / FX）
- 每账户详情含 balance / positions / orders / executions
- Portfolio 以 USD 汇总（演示汇率：CNY=0.139、USD=1.0）
- Reconciliation 状态为 `CONSISTENT`
- 全部操作可审计（AuditCenter）

## 21. 监控与日志

```bash
# Prometheus
open http://localhost:9090/targets
docker compose ps --format "table {{.Name}}\t{{.Status}}"

# 日志
docker logs -f icyquant-api
docker logs -f icyquant-reconciliation
docker logs --tail 200 icyquant-<service>
```

## 22. 故障排查

### 22.1 端口冲突

```bash
netstat -ano | findstr :8000        # Windows
lsof -i :8000                       # macOS / Linux
```

占用时更换本地映射端口（仅开发用）或停止占用进程。

### 22.2 容器未全部 healthy

```bash
docker compose ps
docker logs icyquant-<异常服务>
```

常见原因：API 启动时 `alembic upgrade head` 失败、DB 尚未就绪（启动顺序已由 `depends_on` 保证）。

### 22.3 Gate 在本地裸跑报 DNS 错误

Gate 依赖 compose 服务名（`api`、`database`、`event-bus`、`monitoring`）。请改在容器内执行：

```bash
docker compose exec api python -m apps.runtime gate
```

### 22.4 alembic 迁移失败

```bash
docker compose logs icyquant-api | findstr /i "alembic"   # Windows
docker compose logs icyquant-api | grep -i alembic        # macOS / Linux
```

确认 `alembic.ini` 与 `apps/api` 的 DB 连接串一致，必要时 `alembic downgrade -1` 后重试。

### 22.5 pytest 导入报错（platform 遮蔽）

`tests/platform/` 会遮蔽标准库，必须使用：

```bash
python -m pytest tests/test_dashboard_gate.py -v --import-mode=importlib
```

不要省略 `--import-mode=importlib`。

### 22.6 Git 推送被拒 / 网络超时

```bash
git pull --rebase origin develop    # 先对齐远端
git push origin develop
```

若 `SSL_read: Connection was reset` 或 `443 Timed out`，属网络抖动：确认 `git log origin/develop` 是否已含目标提交，避免重复推送。

## 23. Feature Freeze 政策

v0.4.0-alpha2 进入 **Feature Freeze**，允许的变更仅限：

| 类别 | 允许 |
|---|---|
| 缺陷修复 | 是 |
| 测试补强 | 是 |
| 文档（含本 Runbook） | 是 |
| 配置修正 | 是 |
| 新功能 / 新 API | 否（需 RFC + 排期下个版本） |

任何代码变更必须满足：

1. `python -m apps.runtime scenarios` → 8/8 PASS
2. `python -m apps.runtime gate` → 21/21 PASS
3. `python -m pytest tests/test_dashboard_gate.py tests/test_adapter_gate.py --import-mode=importlib` → 15/15 + 12/12 PASS
4. 提交信息遵循 Conventional Commits，推送前 `git pull --rebase origin develop`

## 24. 验收记录表

每次部署将下表结果填入并附在发布记录中：

| 关卡 | 命令 | 期望 | 实测 |
|---|---|---|---|
| 部署健康 | `docker compose ps` | 10/10 healthy | |
| 聚合健康 | `curl :8000/health` | 10 services UP | |
| Golden | `python -m apps.runtime scenarios` | 8/8 | |
| Readiness | `python -m apps.runtime gate` | 21/21 | |
| Dashboard | `pytest tests/test_dashboard_gate.py --import-mode=importlib` | 15/15 | |
| Adapter | `pytest tests/test_adapter_gate.py --import-mode=importlib` | 12/12 | |
| Paper | `python -m apps.runtime paper --signals 50` | PASS | |
| Shadow | `python -m apps.runtime shadow --signals 20` | PASS | |
| 版本对齐 | `python -c "from shared.constants import APP_VERSION; print(APP_VERSION)"` | 0.4.0-alpha2 | |

## 25. 参考文档

- 架构：`docs/architecture.md`
- 部署：`docs/deployment.md`
- 运维：`docs/operator_guide.md`
- 可观测性：`docs/observability.md`
- 排障：`docs/troubleshooting.md`
- 变更记录：`CHANGELOG.md`
