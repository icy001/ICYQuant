# HistData Stage D 输入 M1 字段 Schema 枚举草案（P0-15 准备物）

> **用途**：`docs/design/histdata_stage_d_phase0_design.md` v8 §10.2 **P0-15** 的枚举草案——"输入 M1 字段 Schema（必需字段、类型、合法值范围）的批准与版本固定"。
>
> **责任角色**：CA（数据覆盖审批人，与 DQA 协同）。**CA 当前未登记**（P0-11 未完成），故本文件为**未批准的枚举草案**。
>
> **完成条件（v8 §10.2 P0-15）**："Schema 已枚举、获批准并具有版本号；与 §6.2.2 D-G02 (1) 的'已批准 Schema'条件形成可追溯对应"。
>
> **依据**：v8 §6.2.2 D-G02、§10.2 P0-15；**实证来源**：`scripts/histdata/stage01/_g11_common.py`（line 670 起）、`docs/02-technical/HISTDATA_DATA_SOURCE.md`。
>
> **状态**：**草案（未批准）**。未获批准前，§6.2.2 D-G02 的"已批准 Schema"条件不成立，D-G02 保持 NOT ASSESSED。

---

## 1. 原始输入格式（HistData ASCII M1）

实证来源：`scripts/histdata/stage01/_g11_common.py`

| 常量 | 值 | 含义 |
|---|---|---|
| `HISTDATA_DELIM` | `";"` | 字段分隔符 |
| `HISTDATA_FIELD_COUNT` | `6` | 固定字段数（严格校验） |
| `HISTDATA_TS_FORMAT` | `"%Y%m%d %H%M%S"` | 原始时间戳格式 |
| 行布局 | `YYYYMMDD HHMMSS;O;H;L;C;V` | 6 字段 |

原始文件命名（`docs/02-technical/HISTDATA_DATA_SOURCE.md`）：`DAT_ASCII_EURUSD_M1_*.{csv,txt}`，2000–2026，每币种每月一个 `.zip`（内含 CSV + TXT 一对）。

---

## 2. 输入 M1 字段清单（P0-15 直接对象）

| # | 字段 | 原始类型 | 原始格式 | 规范类型 | 合法值范围（草案） | 必需 | 实证来源 |
|---|---|---|---|---|---|---|---|
| 1 | 时间戳（原始字段 0） | string | `%Y%m%d %H%M%S` | string（规范形 `%Y-%m-%dT%H:%M:%S`） | 可被格式解析；无时区（按 v8 时间语义为 UTC） | **是** | parse_histdata_line |
| 2 | `open` | float | 十进制 | float64 | `> 0` | **是** | NEGATIVE_PRICE 校验 |
| 3 | `high` | float | 十进制 | float64 | `> 0`；`≥ max(open, close)` | **是** | BAD_OHLC 校验 |
| 4 | `low` | float | 十进制 | float64 | `> 0`；`≤ min(open, close)` | **是** | BAD_OHLC 校验 |
| 5 | `close` | float | 十进制 | float64 | `> 0` | **是** | NEGATIVE_PRICE 校验 |
| 6 | `volume` | float | 十进制 | float64 | `≥ 0` | **是** | BAD_VOLUME 校验 |

**规范时间戳**（`_g11_common.py`）：

| 常量 | 值 |
|---|---|
| `CANONICAL_HASH_TS_FORMAT` | `"%Y-%m-%dT%H:%M:%S"` |
| `CANONICAL_TS_PATTERN` | `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$` |

**数值策略**（`_g11_common.py`）：

| 常量 | 值 |
|---|---|
| `CANONICAL_HASH_FLOAT_POLICY` | exact float64（json shortest round-trip repr）；**no rounding** |
| `CANONICAL_HASH_NULL_POLICY` | **forbidden（fail-closed）** |
| `CANONICAL_HASH_JSON_KWARGS` | `ensure_ascii=False, separators=(",", ":"), allow_nan=False` |

---

## 3. 硬性结构规则（现有实现已强制，供 §6.2.2 D-G02 核对）

实证来源：`parse_histdata_line()` 的错误码。

| 规则 | 错误码 | 判据 | 对应 v8 §6.2.2 D-G02 必需 PASS 条件 |
|---|---|---|---|
| 字段数严格为 6 | `BAD_FIELD_COUNT` | `len(split(";")) == 6`；空行亦报此码 | (1) 字段与已批准 Schema 一致 |
| 时间戳可解析 | `BAD_TIMESTAMP` | 符合 `%Y%m%d %H%M%S` | (1) |
| 数值可解析 | `ENCODING_ERROR` | 5 个数值字段均可转 float | (1) |
| 价格为正 | `NEGATIVE_PRICE` | `open/high/low/close > 0` | (3) 价格为正，非正价格已隔离且理由可追溯 |
| OHLC 关系成立 | `BAD_OHLC` | `high ≥ max(open, close)` 且 `low ≤ min(open, close)` | (2) OHLC 关系成立 |
| 成交量非负 | `BAD_VOLUME` | `volume ≥ 0` | —（v8 §6.2.2 D-G02 未单列；**待 CA 确认是否纳入批准 Schema 的合法值范围**） |

**注意**：v8 §6.2.2 D-G02 明示"第 (1)(2)(3) 项所依据的硬性结构规则清单须经 DQA 批准后方可作为正式 FAIL 判据"（对应 P0-05）。本节的规则清单为**现有实现事实**，其**批准**属 P0-05，**不**属 P0-15。P0-15 的对象是**字段、类型与合法值范围**本身。

---

## 4. 规范输出字段（Stage 02 evidence parquet，交叉引用）

`M1_EVIDENCE_COLUMNS`（`_g11_common.py` line 670，Stage 02 聚合前写出的证据 parquet 物理布局）：

| # | 列名 | 说明 | 是否属 P0-15 输入 Schema |
|---|---|---|---|
| 1 | `ts` | 规范时间戳 | 是（输入字段 1 的规范形） |
| 2 | `open` | — | 是 |
| 3 | `high` | — | 是 |
| 4 | `low` | — | 是 |
| 5 | `close` | — | 是 |
| 6 | `volume` | — | 是 |
| 7 | `source_file` | 输入文件定位 | **否**（证据列；v8 §5.1 最低证据要求，属 P0-10 / PI-02） |
| 8 | `source_line` | 输入行号 | **否**（同上） |
| 9 | `quarantined` | 隔离标记 | **否**（同上） |

**分界说明**：

- **P0-15（本文件）**：输入 M1 字段 Schema —— 前 6 列（`ts`/`open`/`high`/`low`/`close`/`volume`）+ 原始 ASCII 6 字段。
- **P0-10 / PI-02（不在本文件范围）**：§5.1 所列证据字段（`source_file` / `source_line` / `reason` / `threshold` / `dev_prev` / `dev_next` / `prev_close` / `next_close` / `rule_version` / `input_dataset_id` / `event_id` 等）——其逐条确认归 P0-10，最终 schema / 字段映射 / 兼容策略 / `event_id` 取舍归 PI-02。
- **§5.1 明示**："若当前 G11 契约中的字段名称不同，实施前应以实际定义为准进行字段映射；本设计不在此阶段修改任何写出器。"

---

## 5. 与 §6.2.2 D-G02 (1) 的可追溯对应（P0-15 完成条件的第二部分）

v8 §6.2.2 D-G02 必需 PASS 条件：

> "(1) 字段与已批准 Schema 一致（见 §10.2 P0-15）"

| # | 建立对应所需内容 | 现状 | 待办 |
|---|---|---|---|
| 5.1 | Schema 枚举（字段 + 类型 + 合法值范围） | 本文件 §2 已枚举（**未批准**） | — |
| 5.2 | Schema 版本号 | **缺失** | CA 批准时赋予（见 §6） |
| 5.3 | 批准记录（L2） | **载体尚未建立**（PRE-IMPL 必决） | 建立 L2 载体后登记 |
| 5.4 | D-G02 (1) 检核对该 Schema 的引用方式 | 未定义 | 在 D-G02 检查实现中引用 Schema 版本号（属实施阶段） |
| 5.5 | 字段名与现有 G11 契约的映射 | §5.1 已提示"以实际定义为准" | 属 PI-02，不阻塞 P0-15 |

---

## 6. 版本固定建议（待 CA 决定）

| 项 | 建议 | 说明 |
|---|---|---|
| Schema ID | `m1_input_schema_v1` | 与 `BAR_STORAGE_VALIDATOR_ID = "bar_storage_v1"` 命名风格一致 |
| 版本号 | `v1`（首次批准） | 变更须递增版本并保留留痕（v8 §7"规则内容变更时必须递增版本号并保留变更留痕"） |
| 固定对象 | 字段名集合 + 类型 + 合法值范围 + 数值策略（float64 / no rounding / null forbidden） | — |
| 与 `CONTRACT_VERSION = "9.1"` 的关系 | **待 CA 决定**：Schema 版本是否独立于契约版本 | 现有契约版本为 `9.1`（`_g11_common.py`） |

---

## 7. 批准记录字段（L2，待建立登记）

v8 §7"记录位置"第 2 条要求 L2 登记：批准结论、批准角色持有人、规则版本、生效时间、生效范围。本 Schema 的 L2 登记项建议：

| 字段 | 值 |
|---|---|
| 批准对象 | 输入 M1 字段 Schema（本文件 §2） |
| Schema ID / 版本 | 待填 |
| 批准角色 | CA（与 DQA 协同） |
| 批准角色持有人 | 待填（依赖 P0-11） |
| 批准结论 | 待填 |
| 生效时间 / 生效范围 | 待填 |
| 依据 | 本文件 + `_g11_common.py` 实证 + HistData 格式说明 |

---

## 8. 待 CA 决策项（本草案未决）

| # | 决策项 | 草案默认 | 需 CA 确认 |
|---|---|---|---|
| 8.1 | `volume ≥ 0` 是否纳入批准 Schema 的合法值范围 | 建议纳入（现有实现已强制） | ☐ |
| 8.2 | 原始时间戳无时区——是否明确其语义为 UTC | 是（依 v8 时间语义：源 EST、规范 UTC） | ☐ |
| 8.3 | 是否允许 `volume = 0` | 允许（现有实现：`volume ≥ 0`） | ☐ |
| 8.4 | 是否允许缺失值（null） | 禁止（`CANONICAL_HASH_NULL_POLICY = "forbidden (fail-closed)"`） | ☐ |
| 8.5 | 数值精度策略是否固定为 exact float64（no rounding） | 建议固定 | ☐ |
| 8.6 | `source_file` / `source_line` / `quarantined` 是否纳入本 Schema 或归 PI-02 | 建议归 PI-02（证据列） | ☐ |
| 8.7 | Schema 版本是否独立于契约版本 `9.1` | 建议独立 | ☐ |
| 8.8 | 原始文件命名模式是否属本 Schema 范围 | 否（属数据来源登记） | ☐ |

---

## 9. 关联文件

| 文件 | 关系 |
|---|---|
| `docs/design/histdata_stage_d_phase0_design.md`（v8，`85817d33`） | §6.2.2 D-G02 (1)"已批准 Schema"；§5.1 证据字段；§10.2 P0-15 / P0-05 / P0-10 / PI-02 |
| `docs/design/histdata_stage_d_role_appointment_registry.md`（`58bf76c2`） | P0-11 CA 登记（本文件前置） |
| `docs/02-technical/HISTDATA_DATA_SOURCE.md`（`8ff0ada8`） | 数据来源、格式、覆盖年份、抓取与落盘记录 |
| `scripts/histdata/stage01/_g11_common.py` | 实证：`M1_EVIDENCE_COLUMNS`（line 670）、`parse_histdata_line()`（line 907 起）、`HISTDATA_*` 常量（line 902–905）、`CANONICAL_HASH_*` 常量（line 661–667） |

---

**边界声明**：本文件为**枚举草案**，**不**构成 Schema 批准、**不**构成 P0-15 的完成、**不**建立 L2 载体、**不**使 D-G02 脱离 NOT ASSESSED、**不**批准任何 PC-5 数值、**不**构成 Phase 0 通过或实施授权；**不**修改任何代码、写出器或既有契约（`artifacts/histdata_v9/quality_contract.yaml`）。
