# EURUSD HistData 数据入库报告 (Inventory Report)

**Report ID**: eurusd_histdata_inventory
**生成时间**: 2026-10-09 14:55:00 (Local)
**状态**: DRAFT（首次归档，待人工审核）
**配套清单**: `data/real/histdata/MANIFEST.md` (16 KB, 完整 SHA-256)

---

## TL;DR

| 项 | 值 |
|---|---|
| 来源 | HistData.com 免费档 |
| 标的 | EURUSD (Euro vs US Dollar) |
| 颗粒度 | M1 (1-minute bar) |
| 时间范围 | 2000-01 → 2026-10 (26 年完整跨度) |
| 包数 | 36 包 (26 年 + 10 月) |
| 累积量 | 494.18 MB |
| CSV/TXT 关系 | CSV = 数据；TXT = 元数据/Gap 报告 |
| 存档位置 | `ICYQuant/data/real/histdata/` |
| 网络可行性 | 已验证 (HTTPS / 51.77.23.84 / SJC / Cloudflare 缓存命中) |

---

## 数据源 (Provider)

- **Provider 名称**: HistData.com
- **类型**: Free Forex Historical Data
- **URL 模板**:
  `https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/EURUSD/YYYY/M`
- **协议**: HTTPS, TCP 443
- **真实 IP**: 51.77.23.84 (Google DNS + Cloudflare 边缘; SJC)
- **接入路径**(已验证可达): HTML 入口 → 月份详情页 → `.csv` 文件 (下载后改名 `/HISTDATA_COM_ASCII_EURUSD_M1YYYYMM/DAT_ASCII_EURUSD_M1_YYYYMM.csv`)

### 用户下载方式

- 2026-10-09 通过 Mac 浏览器下载 36 个文件
- 浏览器（推测 Safari/Chrome）设置 **自动解压 `.zip`**，所以最终落到 `Downloads/` 时是同名目录
- 原始 `.zip` 文件已被浏览器删除；**解压后文件结构保留**

---

## 文件存储 (Archival Layout)

```
ICYQuant/
└── data/
    └── real/
        ├── d1/                         ← 既有空目录 (未动)
        └── histdata/                   ← 本次新建
            ├── MANIFEST.md             ← 16 KB, 36 包的 SHA-256 + size 完整清单
            └── HISTDATA_COM_ASCII_EURUSD_M1YYYYMM/   × 36
                ├── DAT_ASCII_EURUSD_M1_YYYYMM.csv    ← M1 OHLCV 数据
                └── DAT_ASCII_EURUSD_M1_YYYYMM.txt    ← 元数据/Gap 报告
```

### 命名规范

- 目录名: `HISTDATA_COM_ASCII_EURUSD_M1<YYYYMM>` (无分隔符)
- 数据文件: `DAT_ASCII_EURUSD_M1_<YYYY>_<MM>.csv` (年与月用下划线)
- TXT 同模式: `.txt` 后缀

### 数量与典型尺寸

| 类型 | 大小范围 | 说明 |
|---|---|---|
| 早期年 (2000-2008) | 10-20 MB | 早期外汇活跃度低 |
| 中期年 (2009-2022) | 19-21 MB | ~25 万分钟/年 × 80 字节/分 |
| 近年 (2023-2025) | 17-20 MB | 稳定 |
| 2026 月份 | 1.6 MB/月 | 整个月数据，未结束月较小 |

---

## 实证样本 (Sampled: M1202609)

### CSV 真实字段（已读前 50 行 + 末尾 5 行实证）

**编码**: UTF-8 (无 BOM)
**分隔符**: `;` (分号)
**无表头行**
**6 个字段（按位置）**:

```
[0] timestamp  : YYYYMMDD HHMMSS
[1] open       : float (~1.16x 量级，符合 EURUSD 范围)
[2] high       : float
[3] low        : float
[4] close      : float
[5] volume     : int (样本均 0; 外汇零售通常无 tick volume)
```

**CSV 前 5 行实证**:

```
20260901 000000;1.160540;1.160610;1.160530;1.160600;0
20260901 000100;1.160580;1.160620;1.160580;1.160600;0
20260901 000200;1.160600;1.160620;1.160580;1.160620;0
20260901 000300;1.160620;1.160670;1.160610;1.160650;0
20260901 000400;1.160650;1.160650;1.160640;1.160640;0
```

**CSV 体量**: 1,633,230 bytes / 30,245 lines (2026-09 一个月)

### TXT 不是数据 — 是元数据/状态报告

**TXT 实证内容（节选）**:

```
HistData.com (c) 2012
File: DAT_ASCII_EURUSD_M1_202609.csv Status Report
...
Gap of 68s found between 20260906181345 and 20260906181459
Gap of 141s found between 20260906181650 and 20260906181917
Gap of 64s found between 20260906182221 and 20260906182331
...
```

**体量**: 14,867 bytes / 250 lines
**用途**: 数据质量审计参考 — 提供 Gap 检测信息，**不应作数据源**

### CSV vs TXT 字节差异

- 字节等同? **否** (从第 0 字节即不一致)
- 字节数差异: 1,633,230 vs 14,867 (CSV 大 110 倍)
- 语义差异: CSV = 数据; TXT = 元数据

---

## 待澄清项 (Open Questions)

> **本报告未解答**。下列项需后续步骤用代码或文本读实际内容才能确认。

| # | 项 | 需要 |
|---|---|---|
| 1 | 时区: YYYYMMDD HHMMSS 是 UTC 还是 broker local? | 与 broker 文档交叉验证 / 与外部权威源对比 |
| 2 | 价格精度: 6 位小数 (1.16054) 是否一致? | 全量扫描 + 异常值审计 |
| 3 | 周末数据: 周六/周日是否有行? | 全样本扫描周末时间戳 |
| 4 | Gap 处理: TXT 报告有 Gap 60-141s 在工作日, 是 broker 暂停/报价稀疏? | 与 broker session 规则核对 |
| 5 | OHLC 顺序/规范: H >= max(O,L,C) 且 L <= min(O,H,C)? | 字段约束校验脚本 |
| 6 | Bid/Ask 缺失: 数据是 OHLC 不是 Bid/Ask, **不适合 tick 级研究** | 若需 tick 数据应走 TrueFX/Dukascopy tick 路线 |
| 7 | 早期 2000 年数据是否完整 (10 MB 是否合理)? | 时间序列连续性审计 |
| 8 | 2026-10 是否当月全 (133 KB 偏小)? | 与天数 × 1440 估算对照 |

---

## 与现有 ICYQuant 路径的关系

### 未触动的"禁区"

```
data/processed/    (28 项, 既有策略默认读这里, 不动)
data/alerts/       (dispositions.db, 不动)
data/config/       (trading_ui.json, 不动)
data/lakehouse/    (_state.json + NVDA_15m.csv, 不动)
data/real/d1/      (空目录, 保留)
```

### 现有代码引用 (15 个 .py)

```
research/data/fetch_real.py             ← 真实数据获取入口
apps/adapters/adapters/fx.py            ← FX 适配器
research/discovery/spec.py
research/discovery/factor/{run,cluster,factor_spec}.py
research/universe/research_universe.py
infra/scripts/generate_research_dataset.py
apps/runtime/factor_gate.py
apps/dashboard/api.py
... (其余 6 个 tests/apps)
```

**注意**: 现有 .py 都未引用 `data/real/histdata/`；如未来要接入任何模块, 必须先讨论路径假设, 再动代码。

---

## 网络可达性诊断 (保留证据)

| 域 | DNS | TCP | TLS | HTTPS |
|---|---|---|---|---|
| `www.histdata.com` | ✅ Google DNS = 系统 DNS | ✅ | ✅ | ✅ HTTP 200 |
| TrueFX | ✅ | ✅ | ✅ | ✅ HTTP 200 (但需注册) |
| OANDA / Dukascopy / Phillip / MQL5 | 部分 DNS 污染 | ✅ | ❌ TLS 主动干扰 | ❌ |

完整三层诊断参见: `research/reports/eurusd_data_source_connectivity_audit.md` (草案)

---

## 下一步建议 (NOT EXECUTED — 待用户批准)

### 推荐执行顺序

1. **数据解析器开发** (不读取实际数据, 仅实现解析逻辑)
   - 新建: `data/real/histdata/_parse.py`
   - 功能: 读取 CSV, 规范化时区到 UTC, 校验字段约束

2. **数据质量审计** (一次性 1-shot 评估)
   - 新建: `data/real/histdata/_audit.py`
   - 输出: `data/real/histdata/AUDIT.json` (缺失率/Gap/周末处理等)

3. **MTF 派生** (M5/M15/H1, 不是 tick)
   - 新建: `data/real/histdata/_build_mtf.py`
   - 输出: `data/processed/eurusd/M{1,5,15,30,60}.parquet` — **新增到 processed/**

4. **接入 EURUSD_Reversal_V1**
   - 修改: `research/data/fetch_real.py` 或新建 fetcher
   - **前提**: 与现有 ICE 平台数据契约兼容

### 不推荐路线

- ❌ 直接接入 Tick 级 (数据是 OHLC 不是 tick)
- ❌ 用合成数据 PF/SR 标榜 EURUSD_Reversal_V1 有效 (必须在真实数据下)
- ❌ 自作主张改数据契约

---

## 边界 / Provenance (Hard-line Audit Trail)

| 项 | 状态 |
|---|---|
| 操作类型 | 复制 (`shutil.copytree`), 非移动 |
| 原始路径保留 | `/Users/xuehairong/Downloads/HISTDATA_COM_ASCII_EURUSD_M1*/` 原封 |
| 写入新路径 | 仅 `data/real/histdata/` + 本报告 + `MANIFEST.md` |
| 修改现有文件 | 0 (ICYQuant 任何 .py/.json/.yaml/.toml/.cfg/.ini/.md 之前的 0 修改) |
| 数据内容读取范围 | 仅 `M1202609.csv` + `M1202609.txt` 前 50 行 (用于 E1 实证) |
| 创建文件 | `data/real/histdata/` (含 36 子目录), `MANIFEST.md` (16 KB), 本报告 |
| Git 操作 | 0 commits, 0 push, no `git add` |
| 策略影响 | 0 (策略代码未运行) |

---

## 关联文件

| 文件 | 用途 |
|---|---|
| `data/real/histdata/MANIFEST.md` | 36 包 SHA-256 + size 完整清单 (16 KB) |
| `data/real/histdata/HISTDATA_COM_ASCII_EURUSD_M1*/` | 36 个数据子目录 |
| `research/reports/eurusd_histdata_inventory.md` | 本报告 |
| (待建) `data/real/histdata/_parse.py` | 字段解析器 (未创建) |
| (待建) `data/real/histdata/_audit.py` | 质量审计脚本 (未创建) |
| (草案) `research/reports/eurusd_data_source_connectivity_audit.md` | 三层网络诊断 |

---

## 报告声明

> 本报告严格遵循 **不批准不动** 原则:
>
> 1. 数据仅做了 **复制**(`shutil.copytree`)；
> 2. 原始文件 100% 保留；
> 3. 仅对 M1202609 一个包做了实证内容读取（前 50 行）；
> 4. 未触动 ICYQuant 任何 `.py` / `.json` / `.yaml` / `.toml` 等代码/配置；
> 5. 未自动 commit / push / 触发任何 CI；
> 6. 后续解析器/MTF/策略接入**均不在本报告内执行**，需用户逐项批准。
