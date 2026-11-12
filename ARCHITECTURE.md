# ARCHITECTURE — 目录定位（归档快照 v1.0.0-archive）

本文只描述现状，不构成重构计划。仓库自 2026-11-12 起处于**归档冻结**状态：
研究线已结题（九条候选策略全部否证），LEAN 本地执行链（P0-03-A）已冻结，
P0-03-B（Live Paper Trading）已决定不做。

## 一、活代码（有证据链支撑，CI 守护）

| 目录 | 定位 | 状态 |
|---|---|---|
| `research/` | 研究流水线：Exp01–13 预登记实验、`discovery/costs.py`（成本单一真相源）、`data/validators.py`（价格值域/跳变校验）、`analytics/metrics.py`（Newey-West HAC） | **冻结，结论已定** |
| `tests/lean/` | P0-03-A 冻结基线（90 项），含 `fill_price == 144.78172417` 逐位回归 | **冻结，CI 守护** |
| `integrations/lean/` | LEAN Engine 集成（K01 signal binding / K02 native event adapter / K03） | **冻结** |
| `artifacts/` | 验收证据入库：`lean_p0_03_a_acceptance/`、`research/FINAL_REPORT.md` 等 | 只增不改 |
| `services/` 核心包 | `services.research`、`services.risk.checker`、`services.scheduler` 等实际可导入的包 | 部分活，见第三节 |

## 二、平台脚手架层（不完整，不要用）

这些目录大多是"平台蓝图"式生成物，规模巨大（`infrastructure/` 单目录
约 1000 个 .py），但相当一部分模块从未完成（空文件、缺符号），与之配套的
测试从未跑过——这正是 `tests/conftest.py` 里排除清单的来源。

| 目录 | 备注 |
|---|---|
| `infrastructure/` | 最大的一块（agents/alerting/audit/cache/communication/security…），部分可导入，部分未完成 |
| `production_platform/` / `platform_runtime/` | 生产平台脚手架，未与冻结基线衔接 |
| `apps/` | API/dashboard/worker 入口，未被任何部署证据引用 |
| `core/` / `common/` / `shared/` / `contracts/` | 与 `services/`、`infrastructure/` 存在职责重叠的小目录（各 5–10 个文件） |
| `deployment/` / `monitoring/` / `infra/` | 部署与观测脚手架 |

**判断原则**：凡是被 `tests/conftest.py` 排除清单引用的测试目录对应的实现层，
都按"未完成"对待。排除清单本身（带原因注释）就是这份不完整度的机器可读版本。

## 三、测试分层的真实现状

```
tests/
├─ 冻结基线（全绿，CI 守护）
│   ├─ lean/               90 项，逐位回归
│   ├─ research/           研究线（costs / validators / metrics / HAC / execution）
│   └─ 其余 ~10k 项         各类单元/集成测试（全绿）
├─ 显式排除 — 收集失败 79 个文件   被测模块/符号从未实现
├─ 显式排除 — 运行失败 46 个文件   测试与实现 API 各自演化，待人工裁定
└─ 显式排除 — hang 目录 2 个      production / alternative_intelligence
```

排除清单见 `tests/conftest.py`（分三段、带原因、可逐条恢复）。

## 四、已知同名冲突（修法已固化）

- `services/research/factor.py` ↔ `services/research/factor/`：Python 包优先，
  文件成死代码。已把内容迁入 `factor/factor_definition.py`。
- `services/risk/rules.py` ↔ `services/risk/rules/`：同上，已迁入
  `rules/legacy_rules.py`（`services/risk/checker.py` 仍在用这套旧规则类）。
- 新增模块时**不要**再造出与包同名的 `.py` 文件。

## 五、若要复活项目

1. 先读 `artifacts/research/FINAL_REPORT.md` 第五节（唯一值得走的路）与第六节
   （负面清单，避免重复劳动）。
2. 再读 `tests/conftest.py` 的排除清单——它精确标注了平台层缺什么。
3. CI（`.github/workflows/ci.yml`）保证：你做的任何改动只要破坏冻结基线，
   立刻红灯。
