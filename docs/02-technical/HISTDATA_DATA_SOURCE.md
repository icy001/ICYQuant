# EURUSD Historical Data (HistData.com) — Data Source Document

> **状态**: G6-1 建议 2 采纳后创建。本文件为 9a208ce3（2026-10-13 "add"）入库的 26 年 EURUSD M1 原始数据**来源**的官方记录。
>
> **创建日期**: 2026-10-15
>
> **创建依据**: G6-1 报告（`docs/reviews/g6-1_evidence_report.md`）§1.5（数据来源文档扫描为空）+ §3 缺口 1（数据来源授权链完全缺失）+ §4 建议 2（采纳 A，含核实前置）。核实前置步骤读取 `research/reports/eurusd_*.md` 完成后本文件创建。
>
> **范围之外**: ① 1fa4a34d 入库的 MT 格式数据来源（见 §5 缺口 2） ② 数据质量评估（由 `data/real/histdata/MANIFEST.md` 与 B+C 流水线产物负责） ③ 数据再分发权利的最终法律意见（需独立法律审查）

---

## 1. 数据来源

| 字段 | 值 |
|---|---|
| 数据提供方 | HistData.com |
| URL | `https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/EURUSD` |
| 数据集 | 1-Minute Bar Quotes (M1, OHLC + Volume) |
| 币种 | EURUSD |
| 文件格式 | ASCII CSV + TXT（每个 .zip 内含一对） |
| 覆盖年份 | 2000 – 2026 |
| 频次 | 每币种每月一个 .zip |

**判定依据**: `research/reports/eurusd_data_source_connectivity_audit.md` §2（2026-10-09 09:20–10:00 时段三层网络诊断）——Dukascopy / Dukascopy Tick 候选 / metatrader5.com / phillipnova.com.sg **全部不可达**（TLS 握手超时，与跨境链路整体拥塞模式一致）；**仅** HistData.com 稳定可达（DNS 200/0.85s、TLS 正常），且页面链接实测列出 2000–2026 全部 EURUSD 月度包。ASCII M1 格式与 `data/real/histdata/EURUSD_M1/DAT_ASCII_EURUSD_M1_*.{csv,txt}` 文件命名一致；覆盖年份与 9a208ce3 入库范围一致。

---

## 2. 抓取与落盘

| 字段 | 值 |
|---|---|
| 抓取时间 | 2026-10-09（per `eurusd_histdata_inventory.md` 关联文件表） |
| 抓取方式 | `shutil.copytree`（**复制，非移动**） |
| 原始路径 | `/Users/xuehairong/Downloads/HISTDATA_COM_ASCII_EURUSD_M1*/`（**100% 保留**） |
| 写入路径 | `data/real/histdata/EURUSD_M1/` |
| 抓取时读取内容范围 | 仅 `M1202609.csv` + `M1202609.txt` 前 50 行（用于 E1 实证） |
| 数据契约影响 | 0（未触动 ICYQuant 任何 `.py` / `.json` / `.yaml` / `.toml` / `.cfg` / `.ini` / `.md`） |

**判定依据**: `research/reports/eurusd_histdata_inventory.md` "边界 / Provenance (Hard-line Audit Trail)" 段。

---

## 3. 入库与跟踪

| 字段 | 值 |
|---|---|
| 首次入库 commit | `9a208ce3`（2026-10-13 10:43:08 +0800），author `icy001 <pkxueyingqi@163.com>`，subject `add`（**无 commit body**） |
| 跟踪文件 | `data/real/histdata/EURUSD_M1/DAT_ASCII_EURUSD_M1_*.{csv,txt}`（2000–2026，42 CSV + 36 TXT = 78 文件） |
| 配套清单 | `data/real/histdata/MANIFEST.md`（16 KB / 36 包 SHA-256 + size 完整清单） |
| 同批入库的 9a208ce3 范围内未核查项 | `research/data/histdata/**`、`scripts/b3_validation/**`（5 文件）——见 §5 缺口 3 |

**G6-1 关联**: 9a208ce3 已被 G6-1 报告 §4 建议 2 归类为「范围外的数据导入」（裁定 A：采纳）。本文件**不**重新定性 9a208ce3 的授权来源——授权链缺口已转化为"已分类的范围外事实"。

---

## 4. License 与再分发

| 字段 | 值 |
|---|---|
| HistData.com 服务条款原文 | **本轮未在仓内文档中找到**（见 §5 缺口 1） |
| 仓内研究文件引述 | 仅 `eurusd_data_source_connectivity_audit.md` §2.1 提"免费 ASCII 数据下载"；**未明**再分发 / 衍生作品 / 商业使用条款 |
| 公开入库是否合适 | **未由本文件定性**；需独立法律审查（见 §5 缺口 1） |

---

## 5. 缺口

1. **License 原文缺失**——Phase 0 通过前**应**补充（来源：histdata.com 官网 / 抓取时记录的截图 / 内部法律意见）。本文件**不**对此作法律意见。
2. **MT 格式数据来源未明**——`1fa4a34d`（2026-10-14 17:17:45 +0800）入库的 `data/real/histdata/EURUSD_M1/DAT_MT_EURUSD_M1_2024.csv`（372,379 行）**不**在本文件覆盖范围。
   - `eurusd_data_source_connectivity_audit.md` §1 显示 Dukascopy 在抓取时**不可达**（TLS 超时），故 MT 格式数据**不**可能直接来自 Dukascopy
   - 最大可能性为 B+C step 2 流水线对 ASCII 数据的格式转换（**未经核实**；`artifacts/histdata_v9_bc/step2/` 内是否有转换脚本、运行日志、转换前后对比记录本轮未核查）
   - G6-1 建议 1 已将 1fa4a34d 归类为「范围外运行产物」，本缺口在该归类下**不阻塞** Phase 0，但应在未来补全
3. `research/data/histdata/**` 与 `scripts/b3_validation/**` 内容性质未核查——9a208ce3 的实际改动未全量读取
4. MANIFEST.md 16 KB / 36 包 ↔ 9a208ce3 实际入库 78 数据文件的对应关系未核对

---

## 6. 关联文件

| 文件 | 用途 | 入库 commit |
|---|---|---|
| `research/reports/eurusd_data_source_connectivity_audit.md` | 三层网络诊断 + 数据源评估 | `9a208ce3` |
| `research/reports/eurusd_histdata_inventory.md` | 抓取操作清单 + 边界声明 | `9a208ce3` |
| `data/real/histdata/MANIFEST.md` | 36 包 SHA-256 + size 完整清单 | `9a208ce3` |
| `docs/reviews/g6-1_evidence_report.md` | G6-1 取证报告（本文件创建依据；§4 建议 2 + §8 裁定记录） | `a3af532f` |
| `docs/design/histdata_stage_d_phase0_design.md` | Stage D Phase 0 设计文档 v8 | `85817d33` |

---

## 7. 边界声明

本文件**不**构成：

- 对 HistData.com 数据条款的法律意见
- 对 9a208ce3 授权来源的重新定性（G6-1 报告 §8 裁定记录已分类为"已分类的范围外事实"）
- 对 v9 设计文档 §7.7 / §8 的修订（仅作交叉引用，不进入设计内容）
- Phase 0 通过判定
- 任何 P0-01~P0-15 的 PASS 判定
- 对 26 年 EURUSD M1 数据准入 D-G07 的判定

本文件**仅**为：

- 9a208ce3 入库数据的**来源溯源记录**
- License / 再分发研究的**起点**（**非**结论）
- 未来 G6-2 / 正式评审记录引用时的**事实参考**
