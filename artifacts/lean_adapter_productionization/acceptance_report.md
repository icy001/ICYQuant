# LEAN Adapter Productionization — Acceptance Report

- **Productionization Gate: PASS / CLOSED**（2026-09-30）
- 前序基线：P0-03-A Local Backtest Execution Path = PASS / CLOSED
- 本报告为纯验收与证据汇总，**未改任何业务代码，未重跑任何 backtest**

## 最终结论（严格区分两件事）

| 事项 | 结论 |
|---|---|
| **LEAN Adapter Productionization** | ✅ **PASS / CLOSED** |
| **Live Paper Trading** | ⛔ **PENDING** — QuantConnect Org / live data credentials 未配置（`user-id` / `api-token` 均 `<not set>`） |

```text
Local execution → native event → ICYQuant → EXECUTION → Ledger → Reconciliation
                                                   ↑              ↑
                                             balanced=true  reconciled=true
```

## Gate 链

```text
K01 Signal Binding        PASS / CLOSED
        ↓
K02 Native Event Adapter  PASS / CLOSED
        ↓
K03 Ledger                PASS
K03 Reconciliation        PASS
        ↓
Productionization Gate    PASS  ← 本报告
```

## 证据汇总

### K01 — Signal Binding

- **问题**：`MarketOrder()` 同步触发 `OnOrderEvent` 时 `signal_by_order[order_id]` 尚未写入 → `ICYQUANT_ORDER_EVENT` 的 `signal_id` 为空
- **修复**：预暂存 `signal_id` + 回调首次见到 order_id 时认领（`integrations/lean/paper/main.py`）
- **证据**：`backtests/2026-09-30_14-15-35/1350234380-log.txt` — Submitted(status=1) 与 Filled(status=3) 均携带 `signal_id=p0_buy_spy`
- **基线保护**：`fill_price=144.78172417`、`cash=985520.827583` 与 P0-03-A 基线逐位一致

### K02 — Native Event Adapter

- **组件**：`apps/adapters/lean/native_events.py`（唯一 native→canonical 转换层）；`load_events()` 检测 native 格式（`source=lean-native-json`）
- **冻结边界**：`map_order_event` / `event_mapper.py` 零改动
- **signal_id 证据优先级**：(i) 同目录 `*-log.txt` 的 `ICYQUANT_ORDER_EVENT` 证据行 → (ii) `strategy_contract.json`（仅无歧义）→ (iii) 留空不猜
- **测试**：**19/19 PASS**（`tests/lean/test_lean_native_events.py`）

### K03 — Signed Quantity / Fractional Fill / Commission

| 验收项 | 证据 |
|---|---|
| BUY 100 → `filled_quantity=+100` | `test_buy_100_fills_positive_100` + 真实产物 |
| SELL 100 → `filled_quantity=-100` | `test_sell_100_fills_negative_100`（native `fillQuantity` 恒正、方向在 `direction`，adapter 恢复符号） |
| PARTIALLY_FILLED 不截断 | `fillQuantity=50.5` 原样保留；`partiallyFilled` → `PARTIALLY_FILLED` |
| commission 全链 | native `orderFeeAmount=1.0` → `commission=1.0` → `LedgerTrade.commission=1.0` → `PostingEngine` COMMISSION journal（4 entries，balanced） |
- **测试**：**10/10 PASS**（`tests/lean/test_lean_k03_regression.py`）

### G07 / G08 / G09（真实 K01 原生产物，未重跑 backtest）

```bash
python -m apps.runtime lean-paper \
  --events integrations/lean/paper/backtests/2026-09-30_14-15-35/1350234380-order-events.json
# → 7 PASS / 0 FAIL / 1 PENDING of 8
```

- **G07 EXECUTION**：PASS — 1 fill → EXECUTION envelope（`event_source=lean-native-json`）
- **G08 Ledger**：PASS — journal `balanced=true`，`amount=14478.172417000`，`commission="1.0"`
- **G09 Reconciliation**（`artifacts/lean_paper_e2e/reconciliation.json`）：

```json
{
  "expected":         {"p0_buy_spy": "100"},
  "matched":          [{"signal_id": "p0_buy_spy", "signed_quantity": "100"}],
  "unexpected_fills": {},
  "problems":         [],
  "reconciled":       true
}
```

## 测试总账

| 套件 | 结果 |
|---|---|
| K02 | 19/19 PASS |
| K03 | 10/10 PASS |
| 冻结套件 | 86 passed / **4 failed（既有，K03 范围外）** |

### 4 个既有 failure（明确标记，不属于 Productionization failure）

**git stash 对照已证明**：移除 K02/K03 改动后 4 个失败原样存在——根因是 P0-03-A 会话往 `lean.json` 写入 `organization-id` 占位值（`00000000-...`），触发 P02-G06（"lean.json 无 user-specific local-id"）：

```text
test_lean_json_no_user_specific_identity
test_p0_02_suite_grades_seven_of_eight
test_p0_02_report_is_separate_from_p0_01
test_cli_runs_the_p0_02_suite
```

处置：留待后续独立清理（如恢复 lean.json 或调整 P02-G06 对占位值的判定），**不污染本基线**。

### G05 live deploy

继续保持 **PENDING**——设计内行为：live deploy 需要 QC 组织登录，**不作为本地 Productionization failure**。

## Canonical Event Contract（K03 固化，全文见 `native_events.py` 模块头）

- 必填：`type` / `order_id` / `status` / `quantity`（带符号）/ `filled_quantity`（带符号、累计）
- 可选：`symbol` / `fill_price` / `commission` / `message` / `timestamp`
- 不变量：status 可被 `map_order_event` 原样 round-trip；SELL 双双为负；无 fill 时 `fill_price=None`；signal_id 不可确定时留空、绝不猜测

## 收口与下一步

**LEAN Adapter Productionization = PASS / CLOSED。** 技术债 K01/K02/K03 全部清偿，本地执行链成为可复用生产组件。

下一阶段决策（二选一）：
- **P0-03-B / Live Paper Trading** — 前置条件：QuantConnect Org `user-id` + `api-token`
- **既有 4 failures 清理**（lean.json `organization-id` 占位值）— 纯本地，零外部依赖
