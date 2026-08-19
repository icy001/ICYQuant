# ICYQuant 验证报告（Validation Report）

本报告汇总 ICYQuant v0.4.0-alpha2 部署后的全部验证结果。所有验证在本地 Docker Compose 环境实测执行。

- **版本**: v0.4.0-alpha2
- **环境**: production（APP_ENV=production, APP_DEBUG=false）
- **验证日期**: 2026-08-18 ~ 2026-08-19
- **验证方式**: Docker Compose 10 服务 + pytest 门禁测试 + runtime CLI + Research Layer 回测

---

## 1. 结果总览

| # | 验证项 | 结果 | 明细 |
|---|--------|------|------|
| 1 | 部署状态 | PASS | 10/10 healthy |
| 2 | API 核心端点 | PASS | 5/5 HTTP 200 |
| 3 | Dashboard API 端点 | PASS | 7/7 HTTP 200 |
| 4 | Golden Scenarios | PASS | 8/8 |
| 5 | Production Readiness Gate | PASS | 22/22 |
| 6 | Dashboard Gate | PASS | 15/15 |
| 7 | Adapter Gate | PASS | 12/12 |
| 8 | Bootstrap Gate | PASS | 65/65 |
| 9 | 认证登录 | PASS | admin/admin123 获取 token 成功 |
| 10 | Research Layer（Strategy 001） | PASS | Strategy Gate 6/6 + 单元测试 8/8 + research 包测试 122/122 |

**合计：全部 PASS（10/10 + 5 + 7 + 8 + 22 + 15 + 12 + 65 + 6 + 8 + 122 = 280 项检查全部通过）**

---

## 2. 部署状态（10/10 healthy）

```text
NAME                        STATUS
icyquant-api                Up 3 hours (healthy)
icyquant-database           Up 3 hours (healthy)
icyquant-event-bus          Up 3 hours (healthy)
icyquant-execution-engine   Up 3 hours (healthy)
icyquant-monitoring         Up 3 hours (healthy)
icyquant-order-engine       Up 3 hours (healthy)
icyquant-position-ledger    Up 3 hours (healthy)
icyquant-reconciliation     Up 3 hours (healthy)
icyquant-risk-engine        Up 3 hours (healthy)
icyquant-strategy-runtime   Up 3 hours (healthy)
```

服务端口：api `:8000`、monitoring `:9090`、strategy-runtime `:8011`、risk-engine `:8012`、order-engine `:8013`、execution-engine `:8014`、position-ledger `:8015`、reconciliation `:8016`、database `:5432`、event-bus `:6379`。

---

## 3. API 端点（5/5 HTTP 200）

| 端点 | 状态码 | 说明 |
|------|--------|------|
| `/health` | 200 | 聚合健康检查（READY，10 服务全 UP） |
| `/version` | 200 | 版本信息（0.4.0-alpha2, production, stable） |
| `/ready` | 200 | 就绪状态 |
| `/status` | 200 | 运行状态 |
| `/metrics` | 200 | Prometheus 指标 |

## 4. Dashboard API 端点（7/7 HTTP 200）

登录：`POST /api/auth/login`（admin/admin123）→ 返回 `{"token": ...}`，后续请求携带 `Authorization: Bearer <token>`。

| 端点 | 状态码 |
|------|--------|
| `/api/dashboard/overview` | 200 |
| `/api/dashboard/strategies` | 200 |
| `/api/dashboard/risk` | 200 |
| `/api/dashboard/orders` | 200 |
| `/api/dashboard/positions` | 200 |
| `/api/dashboard/accounts` | 200 |
| `/api/dashboard/portfolio` | 200 |

---

## 5. Golden Scenarios（8/8 PASS）

| 场景 | 结果 | 验证点 |
|------|------|--------|
| 01 Normal Trade | PASS | Order/Execution/Position/Ledger 全部正确 |
| 02 Risk Reject | PASS | Order=0，Position 不变，Ledger 不变 |
| 03 Order Reject | PASS | Position 不变，Ledger 不变 |
| 04 Partial Fill | PASS | 40+60=100 无重复，Position=100，Ledger=100 |
| 05 Duplicate Event | PASS | 重复成交被状态机拒绝，Position=1，Ledger=1 |
| 06 Event Loss / Reconciliation | PASS | 检测 INCONSISTENCY → Rebuild → Verify（恢复 100.0） |
| 07 Service Crash Recovery | PASS | Restart → Replay → Rebuild（=100.0）→ Reconcile OK |
| 08 Ledger/Position Mismatch Repair | PASS | Detect → Repair → Verify（Position=100 = Ledger=100.0） |

---

## 6. Production Readiness Gate（22/22 PASS）

### Infrastructure（4/4）
- I-01 全部 10 服务 UP（聚合 /health）：10 个检查，down=none
- I-02 数据库可达：SELECT 1 ok
- I-03 事件总线（Redis）可达：PONG
- I-04 监控（Prometheus）可达：HTTP 200

### Trading（3/3）
- T-01 Golden Scenarios 01-08 100% PASS：8/8
- T-02 Paper metrics：延迟/滑点/成交率齐全，missing=none
- T-03 Shadow trading 10/10 consistent

### Reliability（4/4）
- R-01 重复事件保护（S05）：由 T-01 覆盖
- R-02 服务崩溃恢复（S07）：由 T-01 覆盖
- R-03 事件丢失检测与重建（S06）：由 T-01 覆盖
- R-04 账本/持仓不一致修复（S08）：由 T-01 覆盖

### Security（4/4）
- S-01 生产模式强制（APP_ENV=production, APP_DEBUG=false）
- S-02 非默认 SECRET_KEY 已设置
- S-03 审计日志已启用（AUDIT_LOG_ENABLED=true）
- S-04 数据库仅通过内部服务名访问（DB_HOST=database）

### Operations（4/4）
- O-01 聚合健康端点 READY：10 个服务检查，down=none
- O-02 各引擎健康端点返回 200：bad=none
- O-03 容器 healthcheck 通过
- O-04 Prometheus 抓取目标健康：HTTP 200

### Validation（3/3）
- V-01 Golden Scenarios 01-08 全部 PASS：8/8
- V-02 版本对齐：app=0.4.0-alpha2 = gate=0.4.0-alpha2
- V-03 Strategy 001 backtest（NVDA 15m）report OK：5 trades, return=6.30%, sharpe=2.45

---

## 7. 门禁验收测试（pytest）

### Dashboard Gate（15/15 PASS）

D-01~D-15，覆盖 9 个页面（accounts/portfolio/positions/orders/executions/reconciliation/system/strategies/risk）+ API 数据一致性 + Docker 可部署性（static 资源齐全 + docker-compose 定义 api 服务）。

```text
15 passed, 140 warnings in 0.70s
```

### Adapter Gate（12/12 PASS）

A-01~A-12，覆盖 A股/期货/美股/外汇 4 个适配器的账户、下单、撤单、行情等能力。

```text
12 passed in 0.02s
```

### Bootstrap Gate（65/65 PASS）

基础类型、生命周期、启动检查等 65 项基础验证。

```text
65 passed, 184 warnings in 0.14s
```

### Strategy 001 单元测试（8/8 PASS）

S001 双均线策略：元数据、warmup HOLD、金叉 BUY、死叉 SELL、趋势中不重复发信号、自定义窗口参数化。

```text
8 passed in 0.01s
```

### 合计

```text
100 passed in ~0.90s
```

> 警告均为 `datetime.datetime.utcnow()` 弃用提示，不影响功能。

---

## 8. Research Layer：Strategy 001（2026-08-19 接入）

研究层已端到端接入部署栈，链路为：

```text
data/lakehouse/NVDA_15m.csv（1690 根 15m K 线，确定性合成）
  -> Strategy 001（S001，20/60 双均线金叉/死叉，research/strategy/strategy_001.py）
  -> BacktestRunner（research/backtest/runner.py）
  -> PerformanceReport（research/analytics/report.py）
  -> Strategy Gate（apps/runtime/strategy_gate.py）+ Readiness Gate V-03
```

### Strategy Gate（6/6 PASS）

```text
Strategy S001 (Strategy 001 - NVDA 15m Moving Average Cross) on NVDA 15m: PASS
  [PASS] data file present: /app/data/lakehouse/NVDA_15m.csv
  [PASS] data volume: 1690 bars loaded
  [PASS] equity curve complete: 1690/1690 points
  [PASS] trades generated: 5 trades
  [PASS] metrics computed: return=6.30% dd=0.25% sharpe=2.449 sortino=3.210
  [PASS] capital positive: final equity $531,522
```

### Research 包回归测试（122/122 PASS）

```text
122 passed, 55 warnings in 0.06s
```

覆盖 strategy / backtest / data / portfolio / execution / tradebook / experiments。

> 注：`tests/research/` 下另有 27 处用例依赖 `services.research`（生产研究服务），其
> `factor/feature_engineering.py` 存在预置 `field(default_factory=dict)` 类型遮蔽问题
> （'str' object is not callable），属既有问题，不在本次 Research Layer 接入范围内修复。

---

## 9. 验证命令速查

### runtime CLI（Golden / Paper / Shadow / Strategy / Readiness）

```bash
docker compose exec api python -m apps.runtime scenarios   # Golden Scenarios 8 项
docker compose exec api python -m apps.runtime paper       # 模拟盘
docker compose exec api python -m apps.runtime shadow      # 影子交易
docker compose exec api python -m apps.runtime strategy    # Strategy 001 回测（Research Layer）
docker compose exec api python -m apps.runtime gate        # Readiness Gate 22 项
```

### pytest 门禁（Dashboard / Adapter / Bootstrap / Strategy）

```bash
docker compose exec api sh -c 'mkdir -p /app/tests'
docker cp tests/. icyquant-api:/app/tests/
docker cp data/lakehouse icyquant-api:/app/data/
docker compose exec api python -m pytest \
  tests/test_dashboard_gate.py tests/test_adapter_gate.py tests/test_bootstrap.py \
  tests/test_strategy_001.py \
  -q --import-mode=importlib
docker compose exec api rm -rf /app/tests
```

### 执行注意

1. `.dockerignore` 排除了 `tests/`，必须先 `docker cp` 拷贝进容器
2. 测试必须放在 `/app/tests`（不能放 `/tmp`），否则 D-15 因 `docker-compose.yml` 路径解析失败
3. `tests/platform/` 目录遮蔽标准库 `platform`，必须加 `--import-mode=importlib` 并从 `/app` 运行
4. 登录响应字段为 `token`（非 `access_token`）
5. `python -m apps.runtime strategy` 依赖 `/app/data/lakehouse/NVDA_15m.csv`（宿主
   `data/lakehouse/` 需先 `docker cp` 同步），可用 `infra/scripts/generate_nvda_15m.py` 重新生成

---

## 10. 验证历史记录

| 日期 | 版本 | 验证项 | 结果 |
|------|------|--------|------|
| 2026-08-18 | v0.4.0-alpha2 | 部署 10/10 + API 5/5 + Dashboard API 7/7 + Golden 8/8 + Readiness 21/21 + Dashboard Gate 15/15 + Adapter Gate 12/12 + Bootstrap 65/65 + 认证 | 全部 PASS（143 项） |
| 2026-08-18 | v0.4.0-alpha2 | Paper Trading 模拟盘（100 信号）：fill 85.0% / reject 13.0% / error 2.0%，全链路延迟 82.6μs，滑点 3.81 bps，equity 2,088,651.33，ledger events 85 | PASS |
| 2026-08-18 | v0.4.0-alpha2 | Shadow Trading 影子交易（50 信号）：50/50 consistent，主/影子持仓逐笔一致（AAPL 1090/MSFT 1100/TSLA 1040），ledger events 50/50 | PASS |
| 2026-08-19 | v0.4.0-alpha2 | Research Layer 接入：Strategy 001（NVDA 15m 双均线）回测 5 笔交易，Readiness Gate 21→22，Strategy Gate 6/6 + 单测 8/8 + research 包回归 122/122 | 全部 PASS（280 项累计） |

后续每次验证后请在下方追加记录。
