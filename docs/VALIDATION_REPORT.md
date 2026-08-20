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

### Dashboard Gate（16/16 PASS）

D-01~D-16，覆盖 10 个页面（accounts/portfolio/positions/orders/executions/reconciliation/system/strategies/risk/factor）+ API 数据一致性 + Docker 可部署性（static 资源齐全 + docker-compose 定义 api 服务）。D-16 校验 Factor 因子纸面页（菜单链接、API payload 结构、headline 数字与逐笔日志一致性；`data/real/d1` 未同步时自动 skip）。

```text
16 passed, 140 warnings in 0.70s
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

## 8a. Research Layer：Factor Alpha021 Paper Trading（2026-08-20 接入）

因子线首个候选（Alpha021，唯一在合成 1H 与真实日频数据双向通过 16 项 Factor Gate、
且通过 De-correlation Gate 独立成族的 alpha）已端到端接入纸面交易链路：

```text
data/real/d1/{NVDA,QQQ,SPY}_1d.csv（真实日频，akshare）
  -> Alpha021（research/discovery/factor/formulas.py，REAL_D1 密封窗口）
  -> rolling z-score（120 bars）-> Schmitt 触发仓位
  -> 方向由 TRAIN 段 IC 符号决定（train-only，不碰 OOS）
  -> 仓位变化 -> 纸面交易信号（多头映射：+1 持 100 股，其余空仓）
  -> PaperTradingSession（fill / reject / error / latency / slippage）
  -> Factor Gate（apps/runtime/factor_gate.py，独立 runtime 命令）
```

### Factor Gate（8/8 PASS，2026-08-20）

```text
Factor Alpha021 on NVDA/QQQ/SPY daily: PASS
  [PASS] data files present: 3/3 files in data/real/d1
  [PASS] data volume: NVDA=660, QQQ=660, SPY=660
  [PASS] factor computable: NVDA=98%, QQQ=98%, SPY=98%
  [PASS] orientation learned: NVDA +0.0744 / QQQ +0.0990 / SPY +0.1087（train IC）
  [PASS] positions non-flat: NVDA=14%, QQQ=14%, SPY=14%
  [PASS] signals generated: 220 position changes
  [PASS] paper execution healthy: fill=85.91% reject=11.36% error=2.73%
  [PASS] account solvency: equity $1,270,677.96, ledger events 189
```

已知限制（记录于 gate 报告）：纸面账户不可做空，+1 映射为持 100 股、其余空仓；
容器内运行需先同步 `data/real/d1`（`docker cp data/real/d1 icyquant-api:/app/data/real/`）。

### De-correlation Gate（第 17 项 Gate，2026-08-20 固化进引擎）

16 项 Factor Gate 之后新增去相关步骤：过闸 alpha 的因子值在 train+validation
（OOS 永不触碰）上按跨资产平均 Spearman |corr| 聚类（average linkage，
密封阈值 0.65），每族只保留 pair score 最高者。合成 factor-v1：22 个过闸 alpha
去相关后为 15 族（D1 区间反转超族 5 成员保 Alpha060，D2 动量条件族 4 成员保
Alpha019）；真实 factor-real-d1：1 个过闸（Alpha021）→ 1 族。

---

## 8b. 阶段标志：Factor Discovery v2 闭环完成（2026-08-20）

```text
Alpha101 (101) → Pair Discovery (909) → Validation v2 (16 项 Gate)
    → Robustness/OOS → De-correlation (22 → 15 独立族)
    → Candidate (Alpha021，双向验证 + 独立族)
    → Paper Trading (220 signals / fill 85.91% / ledger 189 events)
```

| 环节 | 结果 |
|---|---|
| Alpha101 / Pair Discovery | 101 alphas × 9 资产 = 909 pairs |
| Validation v2（16 项 Gate，OOS 不参与选择） | 22 候选（合成）/ 1 候选（真实） |
| De-correlation Gate（\|corr\|≥0.65） | 22 → 15 独立族 |
| Alpha021（唯一双向验证 + 独立族） | 晋升 **Paper Candidate** |
| Paper Trading（NVDA/QQQ/SPY 真实日频） | 220 信号 / 189 成交 / 25 拒单 / 6 错误 |
| 测试 | discovery 86/86 + dashboard 16/16 |

**Paper 结果口径（重要）**：经济意义上有效的 headline 是按真实收盘定价
（±3 bps）的回放——equity $1,000,000 → $1,081,183（**+8.12%**，maxDD -5.0%，
88 笔平仓胜率 68%，已实现 +$68,248 / 浮盈 +$12,934）。Factor Gate 输出里的
$1,270,678（+27%）是 session 内部随机游走 feed 的管线级数字，仅用于验证
fill/reject/ledger 链路，不代表收益。已知限制：纸面多头映射 + 拒单仓位漂移
（期末被动持仓 NVDA500/QQQ200/SPY100），+8.12% 中含部分 2024-26 美股 beta。

**下一阶段（Validation，不是扩展）**：
1. Alpha021 连续 Paper Trading 积累样本（每次刷新数据后重跑回放，快照存档）；
2. 观察真实信号稳定性，记录实际 Fill / Reject / Slippage；
3. Paper 结果与回测 Attribution 对账（分解 alpha / beta / cost）；
4. 达标后评估 Shadow Trading，最后才是 Live Candidate。
在 1-3 完成前，不新增 Alpha、不扩展系统。

---

## 9. 验证命令速查

### runtime CLI（Golden / Paper / Shadow / Strategy / Factor / Readiness）

```bash
docker compose exec api python -m apps.runtime scenarios   # Golden Scenarios 8 项
docker compose exec api python -m apps.runtime paper       # 模拟盘
docker compose exec api python -m apps.runtime shadow      # 影子交易
docker compose exec api python -m apps.runtime strategy    # Strategy 001 回测（Research Layer）
docker compose exec api python -m apps.runtime factor      # Alpha021 因子纸面交易（Research Layer）
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
6. `python -m apps.runtime factor` 依赖 `/app/data/real/d1/{NVDA,QQQ,SPY}_1d.csv`
   （宿主 `data/real/d1/` 需先 `docker cp data/real/d1 icyquant-api:/app/data/real/`
   同步），可用 `python -m research.data.fetch_real` 重新抓取

---

## 10. 验证历史记录

| 日期 | 版本 | 验证项 | 结果 |
|------|------|--------|------|
| 2026-08-18 | v0.4.0-alpha2 | 部署 10/10 + API 5/5 + Dashboard API 7/7 + Golden 8/8 + Readiness 21/21 + Dashboard Gate 15/15 + Adapter Gate 12/12 + Bootstrap 65/65 + 认证 | 全部 PASS（143 项） |
| 2026-08-18 | v0.4.0-alpha2 | Paper Trading 模拟盘（100 信号）：fill 85.0% / reject 13.0% / error 2.0%，全链路延迟 82.6μs，滑点 3.81 bps，equity 2,088,651.33，ledger events 85 | PASS |
| 2026-08-18 | v0.4.0-alpha2 | Shadow Trading 影子交易（50 信号）：50/50 consistent，主/影子持仓逐笔一致（AAPL 1090/MSFT 1100/TSLA 1040），ledger events 50/50 | PASS |
| 2026-08-19 | v0.4.0-alpha2 | Research Layer 接入：Strategy 001（NVDA 15m 双均线）回测 5 笔交易，Readiness Gate 21→22，Strategy Gate 6/6 + 单测 8/8 + research 包回归 122/122 | 全部 PASS（280 项累计） |
| 2026-08-20 | v0.4.0-alpha2 | Factor Layer 接入：Alpha021（NVDA/QQQ/SPY 真实日频）因子→纸面交易 220 信号，fill 85.91%，Factor Gate 8/8；De-correlation Gate 固化进 Factor 引擎（合成 22→15 族，真实 1→1）；discovery 测试 86/86 | 全部 PASS |
| 2026-08-20 | v0.4.0-alpha2 | Dashboard 集成 Factor 因子纸面页（#/factor 菜单 + /api/dashboard/factor + 容器内静态历史回放），Dashboard Gate 15→16（host 与容器均 16/16） | 全部 PASS |

后续每次验证后请在下方追加记录。
